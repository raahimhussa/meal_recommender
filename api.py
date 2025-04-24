from flask import Flask, jsonify, request
from meal_recommender import MealRecommender
import json
from datetime import datetime
import random
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from run_recommender import modify_meal_plan

app = Flask(__name__)

def get_mongodb_data():
    """Get data directly from MongoDB"""
    # Load environment variables
    load_dotenv()
    
    # Get MongoDB URI from environment
    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        raise ValueError("MONGO_URI environment variable not set")
    
    try:
        # Connect to MongoDB
        client = MongoClient(mongo_uri)
        
        # Test the connection
        client.admin.command('ping')
        
        # Create or get the database
        db = client.test
        
        # Get the restaurants collection
        restaurants_collection = db.restaurants
        
        # Get all menu items using aggregation pipeline
        pipeline = [
            {"$match": {"campus": {"$in": ["UMD"]}}},
            {"$unwind": "$menu"},
            {"$unwind": "$menu.items"},
            {
                "$lookup": {
                    "from": "meals",
                    "localField": "menu.items",
                    "foreignField": "_id",
                    "as": "mealDetails"
                }
            },
            {"$unwind": "$mealDetails"},
            {"$match": {"mealDetails.nutrients.calories": {"$gt": 0}}},
            {"$match": {"mealDetails._id": {"$ne": None}}},
            {
                "$project": {
                    "mealName": "$mealDetails.name",
                    "mealType": "$mealDetails.type",
                    "ingredients": "$mealDetails.ingredients",
                    "allergens": "$mealDetails.allergens",
                    "dietaryPreferences": "$mealDetails.dietaryPreferences",
                    "serving": "$mealDetails.serving",
                    "calories": "$mealDetails.nutrients.calories",
                    "protein": "$mealDetails.nutrients.protein",
                    "fat": "$mealDetails.nutrients.fat",
                    "carbohydrate": "$mealDetails.nutrients.carbohydrate",
                    "restaurantName": "$name",
                    "restaurantId": "$_id",
                    "category": "$category",
                    "mealId": "$mealDetails._id"
                }
            }
        ]
        
        menu_items = list(restaurants_collection.aggregate(pipeline))
        return menu_items
        
    except Exception as e:
        print(f"An error occurred while connecting to MongoDB: {str(e)}")
        raise

def format_meal_plan(meal_plan):
    """Format the meal plan for display"""
    formatted_plan = []
    
    for day in meal_plan:
        day_info = {
            'day': day['day'],
            'category': day['category'],
            'meals': {}
        }
        
        daily_totals = {
            'calories': 0,
            'protein': 0,
            'carbs': 0,
            'fat': 0
        }
        
        for meal_type in day['meals_by_type']:
            if day['meals_by_type'][meal_type]:
                meals = day['meals_by_type'][meal_type]
                meal_totals = {
                    'calories': 0,
                    'protein': 0,
                    'carbs': 0,
                    'fat': 0
                }
                
                meal_items = []
                for meal in meals:
                    meal_items.append({
                        'name': meal['mealName'],
                        'restaurant': meal['restaurantName'],
                        'calories': meal.get('calories', 0),
                        'protein': meal.get('protein', 0),
                        'carbs': meal.get('carbohydrate', 0),
                        'fat': meal.get('fat', 0)
                    })
                    
                    meal_totals['calories'] += meal.get('calories', 0)
                    meal_totals['protein'] += meal.get('protein', 0)
                    meal_totals['carbs'] += meal.get('carbohydrate', 0)
                    meal_totals['fat'] += meal.get('fat', 0)
                
                day_info['meals'][meal_type] = {
                    'items': meal_items,
                    'totals': meal_totals
                }
                
                daily_totals['calories'] += meal_totals['calories']
                daily_totals['protein'] += meal_totals['protein']
                daily_totals['carbs'] += meal_totals['carbs']
                daily_totals['fat'] += meal_totals['fat']
        
        day_info['daily_totals'] = daily_totals
        formatted_plan.append(day_info)
    
    return formatted_plan

@app.route('/api/meal-recommendations', methods=['POST'])
def get_meal_recommendations():
    try:
        # Get data from request body
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided in request body'
            }), 400

        # Get parameters from request
        goal = data.get('goal', 'maintain')
        target_calories = data.get('target_calories', 2000)
        days = data.get('days', 7)
        option = data.get('option', 1)
        
        # Get meal preferences based on option
        if option == 1:
            # For 19 meals option, get preferred meals
            preferred_meals = data.get('preferred_meals', ['breakfast', 'lunch', 'dinner'])
            if len(preferred_meals) == 3:
                # If all three selected, randomly select one meal to remove from 2 random days
                all_meals = ['breakfast', 'lunch', 'dinner']
                meals_to_remove = random.sample(all_meals, 1)  # Randomly select one meal to remove
                days_to_modify = random.sample(range(3), 2)  # First 3 days are franchise days
            elif len(preferred_meals) == 2:
                # If two selected, remove the unselected one
                all_meals = ['breakfast', 'lunch', 'dinner']
                meals_to_remove = [meal for meal in all_meals if meal not in preferred_meals]
                days_to_modify = range(3)  # All franchise days
            else:
                # If one selected, randomly select one meal from unselected types
                all_meals = ['breakfast', 'lunch', 'dinner']
                unselected = [meal for meal in all_meals if meal not in preferred_meals]
                meals_to_remove = random.sample(unselected, 1)  # Randomly select one meal from unselected
                days_to_modify = range(3)  # All franchise days
        elif option == 2:
            # For 14 meals option, get which meal to remove
            meal_to_remove = data.get('meal_to_remove', random.choice(['breakfast', 'lunch', 'dinner']))
            meals_to_remove = [meal_to_remove]
            days_to_modify = range(7)  # All days
        else:  # option 3
            # For 7 meals option, get which two meals to remove
            meals_to_remove = data.get('meals_to_remove', random.sample(['breakfast', 'lunch', 'dinner'], 2))
            days_to_modify = range(7)  # All days

        # Get data directly from MongoDB
        menu_items = get_mongodb_data()
        
        # Save to temporary JSON file for the recommender
        temp_json = 'temp_menu_data.json'
        with open(temp_json, 'w', encoding='utf-8') as f:
            json.dump(menu_items, f, default=str, indent=2)
        
        # Initialize the recommender with the temporary data
        recommender = MealRecommender(temp_json)

        # User preferences
        user_prefs = {
            'goal': goal,
            'target_calories': target_calories,
            'allergies': [],
            'exercise': 'Regular exercise',
            'preferred_locations': [],
            'novelty_factor': 0.5,
            'dietary_restrictions': []
        }

        # Set user preferences
        recommender.set_user_preferences(user_prefs)

        user_id = "student_123"
        
        # Generate meal plan
        meal_plan = recommender.recommend_meal_plan(user_id, user_prefs, days=days)
        
        # Modify meal plan based on option and meals to remove
        for day_idx in days_to_modify:
            for meal_type in meals_to_remove:
                if meal_type in meal_plan[day_idx]['meals_by_type']:
                    del meal_plan[day_idx]['meals_by_type'][meal_type]
        
        # Get the formatted meal plan
        formatted_plan = recommender.display_meal_plan(meal_plan)
        
        # Clean up temporary file
        os.remove(temp_json)
        
        return jsonify(formatted_plan)

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True) 