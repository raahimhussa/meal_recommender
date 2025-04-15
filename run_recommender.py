# run_recommender.py
from meal_recommender import MealRecommender
import json
from datetime import datetime

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
    
    # Get dietary restrictions
    print("\nDo you have any dietary restrictions?")
    print("1. None")
    print("2. Vegetarian")
    print("3. Vegan")
    print("4. Gluten-free")
    
    while True:
        try:
            choice = int(input("Enter your choice (1-4): "))
            if 1 <= choice <= 4:
                restrictions = {
                    1: [],
                    2: ['Vegetarian'],
                    3: ['Vegan'],
                    4: ['Gluten-free']
                }
                return restrictions[choice]
        except ValueError:
            print("Please enter a valid number (1-4).")

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

def main():
    try:
        # Load the recommender system
        recommender = MealRecommender("test2.json")
        
        # Get user preferences
        dietary_restrictions = get_user_preferences()
        
        # Define base preferences
        user_prefs = {
            'goal': 'maintain',
            'allergies': [],  # No allergies to start with
            'exercise': 'Regular exercise',
            'preferred_locations': [],  # No location restrictions
            'novelty_factor': 0.5,
            'dietary_restrictions': dietary_restrictions
        }

        user_id = "student_123"

        # Get daily meal plan for selected meals
        daily_plan = get_daily_meal_plan(recommender, user_id, user_prefs)
        
        if not daily_plan:
            print("\nNo meal plan could be created. Please try again later.")
            return

    except FileNotFoundError:
        print("Error: Could not find the meal data file (test2.json)")
    except json.JSONDecodeError:
        print("Error: Invalid JSON format in the meal data file")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    main()
