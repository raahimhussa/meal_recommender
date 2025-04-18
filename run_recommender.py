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

def main():
    try:
        # Load the recommender system
        recommender = MealRecommender("test2.json")

        # Get user's weight goal
        goal = get_weight_goal()
        
        # Define base preferences with goal
        user_prefs = {
            'goal': goal,
            'allergies': [],  # No allergies to start with
            'exercise': 'Regular exercise',
            'preferred_locations': [],  # No location restrictions
            'novelty_factor': 0.5,
            'dietary_restrictions': []
        }

        user_id = "student_123"

        # Get daily meal plan
        print("\nFinding the best meal combination for your nutrition requirements...")
        recommendations = recommender.get_recommendations(user_id, user_prefs, num_recommendations=3)
        
        if recommendations:
            print("\n=== Your Daily Meal Plan ===")
            total_calories = 0
            total_protein = 0
            total_carbs = 0
            total_fat = 0
            
            # Map meal types to display names
            meal_type_names = {
                'breakfast': 'Breakfast',
                'lunch': 'Lunch',
                'dinner': 'Dinner'
            }
            
            for i, meal in enumerate(recommendations, 1):
                # Safely get meal details with defaults
                meal_name = meal.get('mealName', 'Unnamed Meal')
                restaurant = meal.get('restaurantName', 'Unknown Restaurant')
                calories = meal.get('calories', 0)
                protein = meal.get('protein', 0)
                carbs = meal.get('carbohydrate', 0)
                fat = meal.get('fat', 0)
                meal_type = meal.get('mealType', 'unknown').lower()
                display_name = meal_type_names.get(meal_type, f'Meal {i}')
                
                print(f"\n{display_name}: {meal_name} from {restaurant}")
                print(f"Calories: {calories}")
                print(f"Protein: {protein}g")
                print(f"Carbs: {carbs}g")
                print(f"Fat: {fat}g")
                
                # Sum up totals
                total_calories += calories
                total_protein += protein
                total_carbs += carbs
                total_fat += fat
            
            print("\n=== Daily Totals ===")
            print(f"Total Calories: {total_calories}")
            print(f"Total Protein: {total_protein}g")
            print(f"Total Carbs: {total_carbs}g")
            print(f"Total Fat: {total_fat}g")
            
            # Calculate macro percentages
            if total_calories > 0:
                print("\n=== Macro Distribution ===")
                print(f"Protein: {(total_protein * 4 / total_calories) * 100:.1f}%")
                print(f"Carbs: {(total_carbs * 4 / total_calories) * 100:.1f}%")
                print(f"Fat: {(total_fat * 9 / total_calories) * 100:.1f}%")
            
            # Display match quality information
            if recommendations and 'match_quality' in recommendations[0]:
                print("\n=== Match Quality ===")
                match_quality = recommendations[0]['match_quality']
                print(f"Goal: {match_quality['goal']}")
                print(f"Calories: {match_quality['calories']}")
                print(f"Protein: {match_quality['protein']}")
                print(f"Carbs: {match_quality['carbs']}")
                print(f"Fat: {match_quality['fat']}")
                print("\nTarget Ranges:")
                print(f"Protein: {match_quality['target_ranges']['protein']}")
                print(f"Carbs: {match_quality['target_ranges']['carbs']}")
                print(f"Fat: {match_quality['target_ranges']['fat']}")
                print(f"Overall Match: {match_quality['overall_match']}")
        else:
            print("\nNo meal combinations found. Please try adjusting your targets or dietary restrictions.")

    except FileNotFoundError:
        print("Error: Could not find the meal data file (test2.json)")
    except json.JSONDecodeError:
        print("Error: Invalid JSON format in the meal data file")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
