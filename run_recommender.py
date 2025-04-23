# run_recommender.py
from meal_recommender import MealRecommender
import json
from datetime import datetime
import random
from dotenv import load_dotenv
import os
from pymongo import MongoClient

# Define meal options by category
MEAL_OPTIONS = {
    'breakfast': ['starbucks', 'jamba juice', 'village juice', 'taco bell'],
    'lunch': ['barberitos', 'qdoba', 'saladworks', 'bojangles'],
    'dinner': ['subway', 'chick-fil-a', 'panera bread', 'panda express']
}

# Define calorie distribution percentages
CALORIE_DISTRIBUTION = {
    'breakfast': 0.4,  # 40%
    'lunch': 0.3,      # 30%
    'dinner': 0.3      # 30%
}

def get_total_calories():
    """Get total daily calories from user"""
    while True:
        try:
            calories = int(input("\nEnter your total daily calories: "))
            if calories > 0:
                return calories
            print("Please enter a positive number.")
        except ValueError:
            print("Please enter a valid number.")

def get_macros():
    """Get macro requirements from user"""
    print("\nEnter your macro requirements (in grams):")
    while True:
        try:
            protein = float(input("Protein (g): "))
            carbs = float(input("Carbs (g): "))
            fat = float(input("Fat (g): "))
            if protein >= 0 and carbs >= 0 and fat >= 0:
                return {
                    'protein': protein,
                    'carbs': carbs,
                    'fat': fat
                }
            print("Please enter non-negative numbers.")
        except ValueError:
            print("Please enter valid numbers.")

def get_meal_times():
    """Get which meals user wants to plan"""
    print("\nSelect meals to plan (can choose multiple):")
    print("1. Breakfast")
    print("2. Lunch")
    print("3. Dinner")
    print("Enter numbers separated by spaces (e.g., '1 2' for breakfast and lunch)")
    
    while True:
        try:
            choices = input("Your choices: ").split()
            selected_meals = []
            for choice in choices:
                if choice == '1':
                    selected_meals.append('breakfast')
                elif choice == '2':
                    selected_meals.append('lunch')
                elif choice == '3':
                    selected_meals.append('dinner')
            
            if selected_meals:
                return selected_meals
            print("Please select at least one meal.")
        except ValueError:
            print("Please enter valid numbers separated by spaces.")

def calculate_meal_calories(total_calories, selected_meals):
    """Calculate calories for each selected meal based on distribution rules"""
    if len(selected_meals) == 1:
        # Single meal gets 100% of calories
        return {selected_meals[0]: total_calories}
    elif len(selected_meals) == 2:
        # Two meals split 50-50
        return {meal: total_calories // 2 for meal in selected_meals}
    else:
        # Three meals use standard distribution
        return {
            meal: int(total_calories * CALORIE_DISTRIBUTION[meal])
            for meal in selected_meals
        }

def get_user_preferences():
    """Get basic user preferences"""
    print("\nLet's set up your meal preferences:")
    
    # No dietary restrictions needed
    return []

def get_meal_recommendations(recommender, user_id, user_prefs, meal_time, target_calories, macros):
    """Get meal recommendations for a specific time"""
    user_prefs['meal_time'] = meal_time
    user_prefs['target_calories'] = target_calories
    user_prefs['macros'] = macros
    
    # Set preferred locations based on meal time
    user_prefs['preferred_locations'] = MEAL_OPTIONS[meal_time]
    
    print(f"\nFinding {meal_time} options...")
    print(f"Available restaurants for {meal_time}:")
    for restaurant in MEAL_OPTIONS[meal_time]:
        print(f"- {restaurant.title()}")
    
    recommendations = recommender.get_recommendations(user_id, user_prefs, num_recommendations=5)
    
    if not recommendations:
        print(f"No {meal_time} options available.")
        return None
        
    # All recommendations will be from the same restaurant
    restaurant = recommendations[0]['restaurantName']
    print(f"\n{meal_time.capitalize()} at {restaurant}:")
    
    total_calories = 0
    total_protein = 0
    total_carbs = 0
    total_fat = 0
    
    for i, meal in enumerate(recommendations, 1):
        print(f"\n{i}. {meal['mealName']}")
        print(f"   Calories: {meal.get('calories', 0)} kcal")
        if meal.get('protein'):
            print(f"   Protein: {meal['protein']}g")
            total_protein += meal['protein']
        if meal.get('carbohydrate'):
            print(f"   Carbs: {meal['carbohydrate']}g")
            total_carbs += meal['carbohydrate']
        if meal.get('fat'):
            print(f"   Fat: {meal['fat']}g")
            total_fat += meal['fat']
        if meal.get('ingredients'):
            print(f"   Key Ingredients: {', '.join(meal['ingredients'][:3])}")
        total_calories += meal.get('calories', 0)
    
    print(f"\nTotal {meal_time.capitalize()} Nutrition:")
    print(f"Calories: {total_calories} kcal")
    print(f"Protein: {total_protein}g")
    print(f"Carbs: {total_carbs}g")
    print(f"Fat: {total_fat}g")
    
    return recommendations

def get_daily_meal_plan(recommender, user_id, user_prefs):
    """Get meal plan for selected meals of the day"""
    # Get user inputs
    total_calories = get_total_calories()
    macros = get_macros()
    selected_meals = get_meal_times()
    
    # Calculate calories for each meal
    meal_calories = calculate_meal_calories(total_calories, selected_meals)
    
    daily_plan = {}
    print("\n=== Your Daily Meal Plan ===")
    
    for meal_time in selected_meals:
        target_calories = meal_calories[meal_time]
        print(f"\nPlanning {meal_time} ({target_calories} calories)...")
        
        recommendations = get_meal_recommendations(
            recommender, user_id, user_prefs, meal_time, target_calories, macros
        )
        if recommendations:
            daily_plan[meal_time] = recommendations
    
    return daily_plan

def get_weight_goal():
    """Get user's weight goal"""
    print("\nWhat is your weight goal?")
    print("1. Maintain Weight")
    print("2. Lose Weight")
    print("3. Gain Weight")
    
    while True:
        try:
            choice = int(input("Enter your choice (1-3): "))
            if choice == 1:
                return 'maintain'
            elif choice == 2:
                return 'lose'
            elif choice == 3:
                return 'gain'
            else:
                print("Please enter a number between 1 and 3.")
        except ValueError:
            print("Please enter a valid number.")

def get_meal_plan_option():
    """Get user's preferred meal plan option"""
    print("\nChoose your meal plan option:")
    print("1. 19 meals (2 days with 2 meals, 5 days with 3 meals)")
    print("2. 14 meals (2 meals per day)")
    print("3. 7 meals (1 meal per day)")
    
    while True:
        try:
            choice = int(input("Enter your choice (1-3): "))
            if choice in [1, 2, 3]:
                return choice
            print("Please enter a number between 1 and 3.")
        except ValueError:
            print("Please enter a valid number.")

def get_meals_to_remove(option):
    """Get which meals to remove based on the selected option"""
    if option == 1:
        print("\nStep 1: Ask for Meal Preferences")
        print("Available meal types:")
        print("1. Breakfast")
        print("2. Lunch")
        print("3. Dinner")
        print("\nWhich of these meal types do you prefer? Select one or more.")
        print("Enter numbers separated by spaces (e.g., '1 2' for Breakfast and Lunch)")
        
        while True:
            try:
                choices = input("Your choices: ").split()
                if not choices:
                    print("Please select at least one meal type.")
                    continue
                    
                # Convert choices to meal types
                selected_meals = []
                for choice in choices:
                    if choice == '1':
                        selected_meals.append('breakfast')
                    elif choice == '2':
                        selected_meals.append('lunch')
                    elif choice == '3':
                        selected_meals.append('dinner')
                    else:
                        print("Please enter valid numbers between 1 and 3.")
                        break
                
                if len(selected_meals) == len(choices):  # All choices were valid
                    if len(selected_meals) == 3:
                        # If all three selected, randomly remove one meal from 2 random days
                        meals_to_remove = random.sample(['breakfast', 'lunch', 'dinner'], 1)
                        return meals_to_remove[0]
                    elif len(selected_meals) == 2:
                        # If two selected, remove the unselected one
                        all_meals = ['breakfast', 'lunch', 'dinner']
                        unselected = [meal for meal in all_meals if meal not in selected_meals]
                        return unselected[0]
                    else:  # If one selected
                        # Remove one random meal from unselected types
                        all_meals = ['breakfast', 'lunch', 'dinner']
                        unselected = [meal for meal in all_meals if meal not in selected_meals]
                        return random.choice(unselected)
            
            except ValueError:
                print("Please enter valid numbers separated by spaces.")
    
    elif option == 2:
        print("\nWhich meal would you like to remove from all days?")
        print("1. Breakfast")
        print("2. Lunch")
        print("3. Dinner")
        
        while True:
            try:
                choice = int(input("Enter your choice (1-3): "))
                if choice in [1, 2, 3]:
                    return ['breakfast', 'lunch', 'dinner'][choice-1]
                print("Please enter a number between 1 and 3.")
            except ValueError:
                print("Please enter a valid number.")
    
    else:  # option 3
        print("\nWhich two meals would you like to remove from all days?")
        print("1. Breakfast")
        print("2. Lunch")
        print("3. Dinner")
        
        while True:
            try:
                choices = input("Enter two numbers separated by space (e.g., '1 2'): ").split()
                if len(choices) == 2 and all(c in ['1', '2', '3'] for c in choices):
                    return [['breakfast', 'lunch', 'dinner'][int(c)-1] for c in choices]
                print("Please enter two valid numbers between 1 and 3.")
            except ValueError:
                print("Please enter valid numbers.")

def modify_meal_plan(meal_plan, option, meals_to_remove):
    """Modify the meal plan based on the selected option"""
    if option == 1:
        # For option 1, we only modify the first 3 days (franchise days)
        franchise_days = meal_plan[:3]
        
        # Randomly select 2 days from the first 3
        days_to_modify = random.sample(range(3), 2)
        
        # Remove the specified meal type from the selected days
        for day_idx in days_to_modify:
            if meals_to_remove in franchise_days[day_idx]['meals_by_type']:
                del franchise_days[day_idx]['meals_by_type'][meals_to_remove]
        
        # Update the meal plan with modified franchise days
        meal_plan[:3] = franchise_days
    
    elif option == 2:
        # Remove specified meal from all days
        for day in meal_plan:
            if meals_to_remove in day['meals_by_type']:
                del day['meals_by_type'][meals_to_remove]
    
    else:  # option 3
        # Remove two specified meals from all days
        for day in meal_plan:
            for meal_type in meals_to_remove:
                if meal_type in day['meals_by_type']:
                    del day['meals_by_type'][meal_type]
    
    return meal_plan

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
        print("Connecting to MongoDB...")
        client = MongoClient(mongo_uri)
        
        # Test the connection
        client.admin.command('ping')
        print("Successfully connected to MongoDB!")
        
        # Create or get the database
        db = client.test
        print(f"Using database: {db.name}")
        
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
        print(f"\nFetched {len(menu_items)} menu items from MongoDB")
        return menu_items
        
    except Exception as e:
        print(f"An error occurred while connecting to MongoDB: {str(e)}")
        raise

def main():
    try:
        # Get data directly from MongoDB
        menu_items = get_mongodb_data()
        
        # Save to temporary JSON file for the recommender
        temp_json = 'temp_menu_data.json'
        with open(temp_json, 'w', encoding='utf-8') as f:
            json.dump(menu_items, f, default=str, indent=2)
        
        # Initialize the recommender with the temporary data
        recommender = MealRecommender(temp_json)

        # Get user's weight goal
        goal = get_weight_goal()
        
        # Get target calories from user
        target_calories = get_total_calories()
        
        # Define base preferences with goal and target calories
        user_prefs = {
            'goal': goal,
            'target_calories': target_calories,
            'allergies': [],  # No allergies to start with
            'exercise': 'Regular exercise',
            'preferred_locations': [],  # No location restrictions
            'novelty_factor': 0.5,
            'dietary_restrictions': []
        }

        user_id = "student_123"

        # Get meal plan option
        option = get_meal_plan_option()
        
        # Get meals to remove based on option
        meals_to_remove = get_meals_to_remove(option)
        
        # Generate 7-day meal plan
        print("\nGenerating your meal plan...")
        
        # Get the meal plan using the new method
        meal_plan = recommender.recommend_meal_plan(user_id, user_prefs, days=7)
        
        # Modify meal plan based on user's choice
        modified_meal_plan = modify_meal_plan(meal_plan, option, meals_to_remove)
        
        # Display the modified meal plan
        recommender.display_meal_plan(modified_meal_plan)

        # Clean up temporary file
        os.remove(temp_json)

    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
