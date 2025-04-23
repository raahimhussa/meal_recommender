from flask import Flask, request, jsonify
from meal_recommender import MealRecommender
from run_recommender import modify_meal_plan_based_on_preferences, get_meal_preferences, modify_meal_plan
import json
from dotenv import load_dotenv
import os
from pymongo import MongoClient

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize the recommender with MongoDB URI
mongo_uri = os.getenv('MONGO_URI')
if not mongo_uri:
    raise ValueError("MONGO_URI environment variable not set")

try:
    # Test MongoDB connection first
    client = MongoClient(mongo_uri)
    db = client.meal_recommender
    meals_collection = db.meals
    
    # Check if database exists and has collections
    print("\nMongoDB Connection Status:")
    print(f"Database exists: {'meal_recommender' in client.list_database_names()}")
    print(f"Collections in database: {db.list_collection_names()}")
    
    # Count documents in meals collection
    meal_count = meals_collection.count_documents({})
    print(f"Number of meals in database: {meal_count}")
    
    if meal_count == 0:
        print("\nWarning: The meals collection is empty. You need to add meal data to the database.")
        print("Please use the MongoDB Compass or mongo shell to add meal data.")
        print("The meals should have the following structure:")
        print("""
        {
            "mealName": "Meal Name",
            "restaurantName": "Restaurant Name",
            "calories": 500,
            "protein": 20,
            "carbohydrate": 50,
            "fat": 10,
            "mealType": "breakfast/lunch/dinner",
            "category": "Franchise/Dining-Halls",
            "ingredients": ["ingredient1", "ingredient2"],
            "allergens": ["allergen1", "allergen2"]
        }
        """)
    
    # Initialize the recommender
    recommender = MealRecommender(mongo_uri)
    print("Successfully connected to MongoDB and initialized MealRecommender")
except Exception as e:
    print(f"Error connecting to MongoDB: {str(e)}")
    raise

@app.route('/api/recommend', methods=['POST'])
def get_recommendations():
    try:
        # Get data from request
        data = request.json
        
        # Extract required parameters
        user_id = data.get('user_id', 'default_user')
        preferences = {
            'goal': data.get('goal', 'maintain'),
            'target_calories': data.get('target_calories'),
            'allergies': data.get('allergies', []),
            'exercise': data.get('exercise', 'Regular exercise'),
            'preferred_locations': data.get('preferred_locations', []),
            'novelty_factor': data.get('novelty_factor', 0.5),
            'dietary_restrictions': data.get('dietary_restrictions', [])
        }
        selected_meals = data.get('selected_meals', ['breakfast', 'lunch', 'dinner'])
        meal_plan_option = data.get('meal_plan_option', 1)  # Default to 19 meals option
        
        # Generate meal plan
        meal_plan = recommender.recommend_meal_plan(user_id, preferences, days=7)
        
        # Modify meal plan based on preferences
        modified_meal_plan = modify_meal_plan_based_on_preferences(meal_plan, selected_meals)
        
        # Modify meal plan based on selected option (19, 14, or 7 meals)
        if meal_plan_option in [1, 2, 3]:
            meals_to_remove = get_meals_to_remove(meal_plan_option)
            modified_meal_plan = modify_meal_plan(modified_meal_plan, meal_plan_option, meals_to_remove)
        
        # Convert meal plan to JSON-serializable format
        serializable_meal_plan = []
        for day in modified_meal_plan:
            serializable_day = {
                'day': day['day'],
                'category': day['category'],
                'meals_by_type': {}
            }
            for meal_type, meals in day['meals_by_type'].items():
                serializable_day['meals_by_type'][meal_type] = [
                    {
                        'mealName': meal['mealName'],
                        'restaurantName': meal['restaurantName'],
                        'calories': meal.get('calories', 0),
                        'protein': meal.get('protein', 0),
                        'carbohydrate': meal.get('carbohydrate', 0),
                        'fat': meal.get('fat', 0),
                        'ingredients': meal.get('ingredients', []),
                        'allergens': meal.get('allergens', []),
                        'serving_size': meal.get('serving_size', '')
                    }
                    for meal in meals
                ]
            serializable_meal_plan.append(serializable_day)
        
        return jsonify({
            'success': True,
            'meal_plan': serializable_meal_plan
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/refresh', methods=['POST'])
def refresh_meals():
    """Endpoint to refresh meal data from MongoDB"""
    try:
        success = recommender.update_meals()
        if success:
            return jsonify({
                'success': True,
                'message': 'Meal data refreshed successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to refresh meal data'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 