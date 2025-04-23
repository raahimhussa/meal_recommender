from flask import Flask, jsonify, request
from meal_recommender import MealRecommender
import json
from datetime import datetime
import random
from dotenv import load_dotenv
import os
from pymongo import MongoClient

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
        
        for meal_type in ['breakfast', 'lunch', 'dinner']:
            if meal_type in day['meals_by_type'] and day['meals_by_type'][meal_type]:
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

@app.route('/api/meal-recommendations', methods=['GET'])
def get_meal_recommendations():
    try:
        # Get query parameters
        goal = request.args.get('goal', 'maintain')
        target_calories = request.args.get('target_calories', 3789, type=int)
        allergies = request.args.get('allergies', '').split(',') if request.args.get('allergies') else []
        exercise = request.args.get('exercise', 'Regular exercise')
        preferred_locations = request.args.get('locations', '').split(',') if request.args.get('locations') else []
        novelty_factor = request.args.get('novelty_factor', 0.5, type=float)
        dietary_restrictions = request.args.get('dietary_restrictions', '').split(',') if request.args.get('dietary_restrictions') else []
        days = request.args.get('days', 7, type=int)
        
        # Validate goal
        if goal not in ['maintain', 'lose', 'gain']:
            return jsonify({
                'status': 'error',
                'message': 'Invalid goal. Must be one of: maintain, lose, gain'
            }), 400
            
        # Validate target calories
        if target_calories < 1000 or target_calories > 5000:
            return jsonify({
                'status': 'error',
                'message': 'Target calories must be between 1000 and 5000'
            }), 400
            
        # Validate novelty factor
        if novelty_factor < 0 or novelty_factor > 1:
            return jsonify({
                'status': 'error',
                'message': 'Novelty factor must be between 0 and 1'
            }), 400
            
        # Validate days
        if days < 1 or days > 14:
            return jsonify({
                'status': 'error',
                'message': 'Days must be between 1 and 14'
            }), 400

        # Get data directly from MongoDB
        menu_items = get_mongodb_data()
        
        # Save to temporary JSON file for the recommender
        temp_json = 'temp_menu_data.json'
        with open(temp_json, 'w', encoding='utf-8') as f:
            json.dump(menu_items, f, default=str, indent=2)
        
        # Initialize the recommender with the temporary data
        recommender = MealRecommender(temp_json)

        # User preferences from query parameters
        user_prefs = {
            'goal': goal,
            'target_calories': target_calories,
            'allergies': allergies,
            'exercise': exercise,
            'preferred_locations': preferred_locations,
            'novelty_factor': novelty_factor,
            'dietary_restrictions': dietary_restrictions
        }

        user_id = "student_123"
        
        # Generate meal plan
        meal_plan = recommender.recommend_meal_plan(user_id, user_prefs, days=days)
        
        # Format the meal plan
        formatted_plan = format_meal_plan(meal_plan)
        
        # Clean up temporary file
        os.remove(temp_json)
        
        return jsonify({
            'status': 'success',
            'parameters': {
                'goal': goal,
                'target_calories': target_calories,
                'allergies': allergies,
                'exercise': exercise,
                'preferred_locations': preferred_locations,
                'novelty_factor': novelty_factor,
                'dietary_restrictions': dietary_restrictions,
                'days': days
            },
            'meal_plan': formatted_plan
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True) 