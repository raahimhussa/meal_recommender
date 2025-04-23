from pymongo import MongoClient
from dotenv import load_dotenv
import os
from bson import ObjectId
import json

def get_all_restaurants(restaurants_collection):
    """Get all restaurant names"""
    return list(restaurants_collection.find({}))

def get_all_menu_items(restaurants_collection, campus='UMD'):
    """Get all menu items using the aggregation pipeline"""
    pipeline = [
        {"$match": {"campus": {"$in": [campus]}}},
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
        },
        {"$sort": {"calories": -1}}
    ]
    
    return list(restaurants_collection.aggregate(pipeline))

def setup_mongodb():
    # Load environment variables
    load_dotenv()
    
    # Get MongoDB URI from environment
    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        raise ValueError("MONGO_URI environment variable not set")
    
    try:
        # Connect to MongoDB
        print("Connecting to MongoDB...")
        client = MongoClient(mongo_uri)
        
        # Test the connection
        client.admin.command('ping')
        print("Successfully connected to MongoDB!")
        
        # Create or get the database
        db = client.test
        print(f"Using database: {db.name}")
        
        # Create or get the collections
        restaurants_collection = db.restaurants
        meals_collection = db.meals
        
        # Get all menu items using the aggregation pipeline
        print("\nFetching menu items using aggregation pipeline...")
        menu_items = get_all_menu_items(restaurants_collection, campus='UMD')
        
        # Save the menu items to a JSON file for the recommender system
        output_file = 'menu_data.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            # Convert ObjectId to string and format with indentation
            json.dump(menu_items, f, default=str, indent=2, ensure_ascii=False)
        
        print(f"\nFetched {len(menu_items)} menu items and saved to {output_file}")
        print("\nSample menu items:")
        for item in menu_items[:3]:  # Show first 3 items
            print(f"\n{item['mealName']} at {item['restaurantName']}")
            print(f"Calories: {item['calories']}, Protein: {item['protein']}g")
        
        return menu_items
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        raise

if __name__ == "__main__":
    setup_mongodb() 