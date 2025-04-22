import json
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict
import random
from datetime import datetime
from itertools import combinations
import re

class MealRecommender:
    def __init__(self, json_file):
        try:
            with open(json_file, 'r') as f:
                self.meals = json.load(f)
            
            # Define meal options by category
            self.meal_options = {
                'breakfast': ['starbucks', 'jamba juice', 'village juice', 'taco bell'],
                'lunch': ['barberitos', 'qdoba', 'saladworks', 'bojangles'],
                'dinner': ['subway', 'chick-fil-a', 'panera bread', 'panda express']
            }
            
            # Ensure all meals have required fields
            for meal in self.meals:
                meal['mealName'] = meal.get('mealName', 'Unnamed Meal')
                meal['restaurantName'] = meal.get('restaurantName', 'Unknown Restaurant')
                meal['calories'] = float(meal.get('calories', 0))
                meal['protein'] = float(meal.get('protein', 0))
                meal['carbohydrate'] = float(meal.get('carbohydrate', 0))
                meal['fat'] = float(meal.get('fat', 0))
                
                # Get original meal type or set to Unknown if not present
                original_type = meal.get('mealType', 'Unknown')
                
                # If meal type is Unknown, try to determine it from restaurant name
                if original_type.lower() == 'unknown':
                    restaurant_name = meal.get('restaurantName', '').lower()
                    for category, restaurants in self.meal_options.items():
                        if any(restaurant.lower() in restaurant_name for restaurant in restaurants):
                            meal['mealType'] = category
                            break
                    else:
                        # If no match found, keep it as Unknown
                        meal['mealType'] = original_type
                else:
                    # Keep the original meal type
                    meal['mealType'] = original_type
                
        except FileNotFoundError:
            print(f"Error: Could not find the meal data file ({json_file})")
            self.meals = []
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON format in the meal data file ({json_file})")
            self.meals = []
        except Exception as e:
            print(f"Error loading meal data: {str(e)}")
            self.meals = []
        
        self.preprocess_data()
        self.initialize_models()
        
    def load_data(self, json_file):
        """Load and parse the JSON data"""
        with open(json_file) as f:
            self.data = json.load(f)
        
        # Create restaurant to meals mapping
        self.restaurant_meals = defaultdict(list)
        for meal in self.data:
            self.restaurant_meals[meal['restaurantName']].append(meal)
        
        # Create unique meal ID for each meal
        for i, meal in enumerate(self.data):
            meal['mealId'] = meal.get('mealId', f"meal_{i}")
    
    def save_history(self, user_id):
        """Save user history to a file"""
        with open(f"{user_id}_history.json", "w") as f:
            json.dump(list(self.user_history[user_id]), f)

    def load_history(self, user_id):
        """Load user history from a file"""
        try:
            with open(f"{user_id}_history.json") as f:
                self.user_history[user_id] = set(json.load(f))
        except FileNotFoundError:
            pass
    
    def preprocess_data(self):
        """Prepare data for analysis"""
        for meal in self.meals:
            # Create a feature string combining important attributes
            features = []
            features.append(meal['mealName'])
            features.extend(meal.get('ingredients', []))
            features.extend(meal.get('allergens', []))
            features.append(meal['mealType'])
            features.append(meal['category'])
            meal['feature_string'] = ' '.join(features).lower()
            
            # Calculate health score (simplified)
            protein = meal.get('protein', 0)
            fat = meal.get('fat', 0)
            carbs = meal.get('carbohydrate', 0)
            calories = meal.get('calories', 0)
            
            # Simple health score (higher is better)
            if calories > 0:
                meal['health_score'] = (protein * 0.5 + (1000 / calories) * 0.3 - fat * 0.1 - carbs * 0.1)
            else:
                meal['health_score'] = 0
    
    def initialize_models(self):
        """Initialize ML models for recommendations"""
        # TF-IDF for content-based filtering
        self.vectorizer = TfidfVectorizer(stop_words='english')
        feature_strings = [meal['feature_string'] for meal in self.meals]
        self.tfidf_matrix = self.vectorizer.fit_transform(feature_strings)
        
        # Calculate similarity matrix
        self.similarity_matrix = cosine_similarity(self.tfidf_matrix)
    
    def load_weekly_history(self):
        """Load weekly meal history from file"""
        try:
            with open("weekly_history.json", "r") as f:
                weekly_data = json.load(f)
                for user_id, meals in weekly_data.items():
                    self.weekly_meals[user_id] = set(meals)
        except FileNotFoundError:
            # File doesn't exist yet, that's okay
            pass
        except Exception as e:
            print(f"Error loading weekly history: {str(e)}")
    
    def save_weekly_history(self):
        """Save weekly meal history to file"""
        try:
            weekly_data = {user_id: list(meals) for user_id, meals in self.weekly_meals.items()}
            with open("weekly_history.json", "w") as f:
                json.dump(weekly_data, f)
        except Exception as e:
            print(f"Error saving weekly history: {str(e)}")
    
    def reset_weekly_history(self, user_id):
        """Reset weekly meal history for a user"""
        self.weekly_meals[user_id].clear()
        self.save_weekly_history()
    
    def get_recommendations(self, user_id, preferences, num_recommendations=3, day_number=None):
        """Get personalized meal recommendations based on weight goal and nutrition requirements"""
        # Get user's goal and calculate target ranges
        goal = preferences.get('goal', 'maintain').lower()
        
        # Define nutrition ranges based on goal with exact specifications
        if goal == 'maintain':
            target_calories = preferences.get('target_calories', 2250)  # Middle of 2000-2500 range
            macro_ranges = {
                'protein': {'min': 0.20, 'max': 0.30},  # 20-30%
                'fat': {'min': 0.20, 'max': 0.35},      # 20-35%
                'carbs': {'min': 0.40, 'max': 0.50}     # 40-50%
            }
        elif goal == 'lose':
            target_calories = preferences.get('target_calories', 1750)  # Middle of 1500-2000 range
            macro_ranges = {
                'protein': {'min': 0.30, 'max': 0.40},  # 30-40%
                'fat': {'min': 0.20, 'max': 0.35},      # 20-35%
                'carbs': {'min': 0.45, 'max': 0.55}     # 45-55%
            }
        elif goal == 'gain':
            target_calories = preferences.get('target_calories', 2750)  # Middle of 2250-3250 range
            macro_ranges = {
                'protein': {'min': 0.25, 'max': 0.35},  # 25-35%
                'fat': {'min': 0.30, 'max': 0.40},      # 30-40%
                'carbs': {'min': 0.45, 'max': 0.55}     # 45-55%
            }
        else:
            # Default to maintain if goal is not specified
            target_calories = preferences.get('target_calories', 2250)
            macro_ranges = {
                'protein': {'min': 0.20, 'max': 0.30},
                'fat': {'min': 0.20, 'max': 0.35},
                'carbs': {'min': 0.40, 'max': 0.50}
            }
        
        # Calculate target calories per meal (divide by 3 for breakfast, lunch, dinner)
        target_calories_per_meal = target_calories / 3
        
        # Calculate target macros in grams per meal
        target_macros_per_meal = {
            'protein': (target_calories_per_meal * macro_ranges['protein']['min']) / 4,  # 4 calories per gram
            'carbs': (target_calories_per_meal * macro_ranges['carbs']['min']) / 4,      # 4 calories per gram
            'fat': (target_calories_per_meal * macro_ranges['fat']['min']) / 9           # 9 calories per gram
        }
        
        # Filter meals based on preferences
        filtered_meals = []
        
        for meal in self.meals:
            # Skip meals with no nutrition data
            if not meal.get('calories') or not meal.get('protein') or not meal.get('carbohydrate') or not meal.get('fat'):
                continue
            
            # Calculate portion size based on serving information
            serving = meal.get('serving', '')
            portion_multiplier = 1.0
            
            # Check if this is a catering/tray meal
            if 'tray' in serving.lower() or 'container' in serving.lower() or 'serves' in serving.lower():
                # Try to extract number of servings
                serves_match = re.search(r'serves\s*(\d+)', serving.lower())
                if serves_match:
                    portion_multiplier = 1.0 / float(serves_match.group(1))
                else:
                    # Default to 10 servings if not specified
                    portion_multiplier = 0.1
            
            # Create a portioned version of the meal
            portioned_meal = meal.copy()
            portioned_meal['calories'] = meal['calories'] * portion_multiplier
            portioned_meal['protein'] = meal['protein'] * portion_multiplier
            portioned_meal['carbohydrate'] = meal['carbohydrate'] * portion_multiplier
            portioned_meal['fat'] = meal['fat'] * portion_multiplier
            portioned_meal['serving_size'] = f"{portion_multiplier:.2f} of {serving}"
            
            # Skip meals that are still too large for a single meal
            if portioned_meal['calories'] > target_calories_per_meal * 1.3:  # Allow up to 130% of target
                continue
                
            filtered_meals.append(portioned_meal)
        
        if not filtered_meals:
            print("No meals passed basic filtering. Using all meals...")
            filtered_meals = self.meals
        
        # Score individual meals first
        scored_meals = []
        for meal in filtered_meals:
            meal_calories = meal.get('calories', 0)
            meal_protein = meal.get('protein', 0)
            meal_carbs = meal.get('carbohydrate', 0)
            meal_fat = meal.get('fat', 0)
            
            if meal_calories == 0:
                continue
            
            # Calculate macro percentages
            protein_percent = (meal_protein * 4 / meal_calories)
            carbs_percent = (meal_carbs * 4 / meal_calories)
            fat_percent = (meal_fat * 9 / meal_calories)
            
            # Score based on how well macros fit target ranges (more precise)
            macro_score = 0
            # Protein score (higher is better)
            if protein_percent < macro_ranges['protein']['min']:
                protein_score = protein_percent / macro_ranges['protein']['min']
            elif protein_percent > macro_ranges['protein']['max']:
                protein_score = 1 - (protein_percent - macro_ranges['protein']['max']) / (1 - macro_ranges['protein']['max'])
            else:
                protein_score = 1.0
            
            # Carbs score
            if carbs_percent < macro_ranges['carbs']['min']:
                carbs_score = carbs_percent / macro_ranges['carbs']['min']
            elif carbs_percent > macro_ranges['carbs']['max']:
                carbs_score = 1 - (carbs_percent - macro_ranges['carbs']['max']) / (1 - macro_ranges['carbs']['max'])
            else:
                carbs_score = 1.0
            
            # Fat score
            if fat_percent < macro_ranges['fat']['min']:
                fat_score = fat_percent / macro_ranges['fat']['min']
            elif fat_percent > macro_ranges['fat']['max']:
                fat_score = 1 - (fat_percent - macro_ranges['fat']['max']) / (1 - macro_ranges['fat']['max'])
            else:
                fat_score = 1.0
            
            macro_score = (protein_score + carbs_score + fat_score) / 3
            
            # Score based on calorie match (more precise)
            calorie_score = 1 - min(abs(meal_calories - target_calories_per_meal) / target_calories_per_meal, 1)
            
            # Add random factor for variety (smaller range for more consistency)
            random_factor = random.uniform(0.9, 1.1)
            
            # Calculate overall score with weights (60% macros, 40% calories)
            overall_score = (macro_score * 0.6 + calorie_score * 0.4) * random_factor
            
            scored_meals.append((overall_score, meal))
        
        # Sort by score
        scored_meals.sort(reverse=True, key=lambda x: x[0])
        
        # Get recommendations for each meal time
        meal_times = ['breakfast', 'lunch', 'dinner']
        all_recommendations = []
        
        for meal_time in meal_times:
            # Filter meals for this meal time
            time_filtered_meals = [(score, meal) for score, meal in scored_meals 
                                 if meal_time.lower() in meal.get('mealType', '').lower()]
            
            if not time_filtered_meals:
                print(f"No {meal_time} meals found, using all meals...")
                time_filtered_meals = scored_meals
            
            # Try different combinations of meals
            for num_meals in range(2, 4):  # Try 2 or 3 meals
                # Select from top 50 meals for better quality
                top_meals = time_filtered_meals[:50]
                random.shuffle(top_meals)
                
                best_combination = None
                best_total_score = float('-inf')
                best_total_match = float('-inf')
                
                # Group meals by restaurant
                restaurant_meals = {}
                for score, meal in top_meals:
                    restaurant = meal.get('restaurantName', 'Unknown Restaurant')
                    if restaurant not in restaurant_meals:
                        restaurant_meals[restaurant] = []
                    restaurant_meals[restaurant].append((score, meal))
                
                # Try combinations from each restaurant
                for restaurant, meals in restaurant_meals.items():
                    if len(meals) < num_meals:
                        continue
                        
                    for meal_combination in combinations(meals, num_meals):
                        total_calories = 0
                        total_macros = {
                            'protein': 0,
                            'carbs': 0,
                            'fat': 0
                        }
                        
                        # Calculate totals for this combination
                        for _, meal in meal_combination:
                            total_calories += meal.get('calories', 0)
                            total_macros['protein'] += meal.get('protein', 0)
                            total_macros['carbs'] += meal.get('carbohydrate', 0)
                            total_macros['fat'] += meal.get('fat', 0)
                        
                        if total_calories == 0:
                            continue
                        
                        # Skip combinations that exceed calorie limit
                        if total_calories > target_calories_per_meal * 1.3:  # Allow 30% flexibility
                            continue
                        
                        # Skip combinations that are too low in calories
                        if total_calories < target_calories_per_meal * 0.7:  # Require at least 70% of target
                            continue
                        
                        # Calculate macro percentages for the combination
                        protein_percent = (total_macros['protein'] * 4 / total_calories)
                        carbs_percent = (total_macros['carbs'] * 4 / total_calories)
                        fat_percent = (total_macros['fat'] * 9 / total_calories)
                        
                        # Skip combinations that don't meet macro requirements
                        if (protein_percent < macro_ranges['protein']['min'] or 
                            protein_percent > macro_ranges['protein']['max'] or
                            carbs_percent < macro_ranges['carbs']['min'] or 
                            carbs_percent > macro_ranges['carbs']['max'] or
                            fat_percent < macro_ranges['fat']['min'] or 
                            fat_percent > macro_ranges['fat']['max']):
                            continue
                        
                        # Score based on macro percentages (more precise)
                        macro_score = 0
                        # Protein score
                        if protein_percent < macro_ranges['protein']['min']:
                            protein_score = protein_percent / macro_ranges['protein']['min']
                        elif protein_percent > macro_ranges['protein']['max']:
                            protein_score = 1 - (protein_percent - macro_ranges['protein']['max']) / (1 - macro_ranges['protein']['max'])
                        else:
                            protein_score = 1.0
                        
                        # Carbs score
                        if carbs_percent < macro_ranges['carbs']['min']:
                            carbs_score = carbs_percent / macro_ranges['carbs']['min']
                        elif carbs_percent > macro_ranges['carbs']['max']:
                            carbs_score = 1 - (carbs_percent - macro_ranges['carbs']['max']) / (1 - macro_ranges['carbs']['max'])
                        else:
                            carbs_score = 1.0
                        
                        # Fat score
                        if fat_percent < macro_ranges['fat']['min']:
                            fat_score = fat_percent / macro_ranges['fat']['min']
                        elif fat_percent > macro_ranges['fat']['max']:
                            fat_score = 1 - (fat_percent - macro_ranges['fat']['max']) / (1 - macro_ranges['fat']['max'])
                        else:
                            fat_score = 1.0
                        
                        macro_score = (protein_score + carbs_score + fat_score) / 3
                        
                        # Score based on calorie match
                        calorie_score = 1 - min(abs(total_calories - target_calories_per_meal) / target_calories_per_meal, 1)
                        
                        # Calculate total match score (70% macro match, 30% calorie match)
                        total_match_score = (macro_score * 0.7 + calorie_score * 0.3)
                        
                        # Calculate combination score (weighted average of individual scores and total match)
                        individual_scores = sum(score for score, _ in meal_combination) / num_meals
                        combination_score = (total_match_score * 0.8 + individual_scores * 0.2)
                        
                        # Update best combination if we find a better score
                        if combination_score > best_total_score:
                            best_total_score = combination_score
                            best_total_match = total_match_score
                            best_combination = meal_combination
                
                # If we found any valid combinations, create a combined meal
                if best_combination:
                    # Create a combined meal from the best combination
                    combined_meal = {
                        'mealName': ' + '.join(meal['mealName'] for _, meal in best_combination),
                        'restaurantName': best_combination[0][1].get('restaurantName', 'Unknown Restaurant'),
                        'calories': sum(meal.get('calories', 0) for _, meal in best_combination),
                        'protein': sum(meal.get('protein', 0) for _, meal in best_combination),
                        'carbohydrate': sum(meal.get('carbohydrate', 0) for _, meal in best_combination),
                        'fat': sum(meal.get('fat', 0) for _, meal in best_combination),
                        'ingredients': list(set(ing for _, meal in best_combination for ing in meal.get('ingredients', []))),
                        'allergens': list(set(allergen for _, meal in best_combination for allergen in meal.get('allergens', []))),
                        'sub_meals': [meal for _, meal in best_combination],
                        'mealType': meal_time
                    }
                    
                    # Calculate final macro percentages
                    final_calories = combined_meal['calories']
                    final_protein = combined_meal['protein']
                    final_carbs = combined_meal['carbohydrate']
                    final_fat = combined_meal['fat']
                    
                    final_protein_percent = (final_protein * 4 / final_calories) * 100
                    final_carbs_percent = (final_carbs * 4 / final_calories) * 100
                    final_fat_percent = (final_fat * 9 / final_calories) * 100
                    
                    # Add match quality information
                    combined_meal['match_quality'] = {
                        'calories': f"{final_calories}/{target_calories_per_meal:.0f} ({((final_calories/target_calories_per_meal)*100):.1f}%)",
                        'protein': f"{final_protein}g ({final_protein_percent:.1f}%)",
                        'carbs': f"{final_carbs}g ({final_carbs_percent:.1f}%)",
                        'fat': f"{final_fat}g ({final_fat_percent:.1f}%)",
                        'goal': goal.capitalize(),
                        'target_ranges': {
                            'protein': f"{macro_ranges['protein']['min']*100:.0f}-{macro_ranges['protein']['max']*100:.0f}%",
                            'carbs': f"{macro_ranges['carbs']['min']*100:.0f}-{macro_ranges['carbs']['max']*100:.0f}%",
                            'fat': f"{macro_ranges['fat']['min']*100:.0f}-{macro_ranges['fat']['max']*100:.0f}%"
                        },
                        'overall_match': f"Score: {best_total_score:.2f}"
                    }
                    
                    all_recommendations.append(combined_meal)
        
        return all_recommendations  # Return all three meals
    
    def filter_meals(self, preferences):
        """Filter meals based on user preferences"""
        filtered = []
        meal_time = preferences.get('meal_time', 'breakfast')
        dietary_restrictions = preferences.get('dietary_restrictions', [])
        preferred_locations = preferences.get('preferred_locations', [])
        
        print(f"\nFiltering meals for {meal_time}...")
        print(f"Target calories: {preferences.get('target_calories', 0)}")
        print(f"Target macros: {preferences.get('macros', {})}")
        
        for meal in self.meals:
            # Skip meals that don't match meal time
            if meal_time.lower() not in meal['mealType'].lower():
                continue
                
            # Skip meals that don't match dietary restrictions
            if dietary_restrictions:
                meal_tags = meal.get('tags', [])
                if any(restriction.lower() in [tag.lower() for tag in meal_tags] 
                      for restriction in dietary_restrictions):
                    continue
            
            # Skip meals from non-preferred locations
            if preferred_locations:
                restaurant_name = meal['restaurantName'].lower()
                if not any(loc.lower() in restaurant_name for loc in preferred_locations):
                    continue
            
            filtered.append(meal)
        
        return filtered
    
    def score_meal(self, meal, preferences, user_history, user_id):
        """Score a meal based on how well it matches preferences"""
        score = 0
        
        # Macro-based scoring (70% weight)
        target_macros = preferences.get('macros', {})
        if target_macros:
            macro_score = 0
            total_macros = 0
            
            for macro, target in target_macros.items():
                if target > 0:
                    meal_value = meal.get(macro, 0)
                    # Use stricter scoring for macros
                    macro_score += 1 - min(abs(meal_value - target) / target, 1)
                    total_macros += 1
            
            if total_macros > 0:
                score += (macro_score / total_macros) * 0.7
        
        # Calorie-based scoring (30% weight)
        target_calories = preferences.get('target_calories', 0)
        if target_calories > 0:
            meal_calories = meal.get('calories', 0)
            # Use stricter scoring for calories
            calorie_score = 1 - min(abs(meal_calories - target_calories) / target_calories, 1)
            score += calorie_score * 0.3
        
        return score
    
    def validate_meal_plan(self, meal_plan, preferences):
        """Validate if the meal plan meets all requirements"""
        validation_results = {
            'calories': True,
            'allergens': True,
            'macros': True,
            'swipes': True,
            'location_rules': True,
            'messages': []
        }
        
        # Check daily totals
        daily_totals = defaultdict(lambda: {
            'calories': 0,
            'protein': 0,
            'carbs': 0,
            'fat': 0,
            'locations': set()
        })
        
        for day in meal_plan:
            day_num = day['day']
            # Get all meals for the day from meals_by_type
            all_meals = []
            for meal_type in ['breakfast', 'lunch', 'dinner']:
                all_meals.extend(day['meals_by_type'].get(meal_type, []))
            
            for meal in all_meals:
                # Track daily totals
                daily_totals[day_num]['calories'] += meal.get('calories', 0)
                daily_totals[day_num]['protein'] += meal.get('protein', 0)
                daily_totals[day_num]['carbs'] += meal.get('carbohydrate', 0)
                daily_totals[day_num]['fat'] += meal.get('fat', 0)
                daily_totals[day_num]['locations'].add(meal['restaurantName'])
                
                # Check allergens
                if any(allergen in meal.get('allergens', []) for allergen in preferences.get('allergies', [])):
                    validation_results['allergens'] = False
                    validation_results['messages'].append(
                        f"Day {day_num}: Meal '{meal['mealName']}' contains allergens"
                    )
        
        # Check daily calorie limits
        target_daily_calories = preferences.get('target_daily_calories', 2000)
        for day_num, totals in daily_totals.items():
            if totals['calories'] > target_daily_calories * 1.1:  # 10% buffer
                validation_results['calories'] = False
                validation_results['messages'].append(
                    f"Day {day_num}: Total calories ({totals['calories']}) exceed daily limit"
                )
            
            # Check macros based on goal
            goal = preferences.get('goal', 'maintain')
            if goal == 'lose':
                if totals['protein'] < totals['carbs'] * 0.8:  # Should have higher protein ratio
                    validation_results['macros'] = False
                    validation_results['messages'].append(
                        f"Day {day_num}: Protein intake too low for weight loss"
                    )
            elif goal == 'gain':
                if totals['protein'] < totals['carbs'] * 0.6:  # Should have even higher protein ratio
                    validation_results['macros'] = False
                    validation_results['messages'].append(
                        f"Day {day_num}: Protein intake too low for muscle gain"
                    )
            
            # Check location rules
            if len(totals['locations']) > 1:
                validation_results['location_rules'] = False
                validation_results['messages'].append(
                    f"Day {day_num}: Multiple locations used in one day"
                )
        
        # Check swipe limits
        total_meals = sum(len(day['meals_by_type'].get('breakfast', [])) + 
                         len(day['meals_by_type'].get('lunch', [])) + 
                         len(day['meals_by_type'].get('dinner', [])) 
                         for day in meal_plan)
        swipe_limit = preferences.get('swipe_limit', 19)
        if total_meals > swipe_limit:
            validation_results['swipes'] = False
            validation_results['messages'].append(
                f"Total meals ({total_meals}) exceed swipe limit ({swipe_limit})"
            )
        
        return validation_results
    
    def is_similar_item(self, item1, item2):
        """Check if two meal items are similar based on their names and ingredients"""
        # Convert to lowercase for comparison
        name1 = item1['mealName'].lower()
        name2 = item2['mealName'].lower()
        
        # Get ingredients lists
        ingredients1 = set(ing.lower() for ing in item1.get('ingredients', []))
        ingredients2 = set(ing.lower() for ing in item2.get('ingredients', []))
        
        # Check for common words in names
        name_words1 = set(name1.split())
        name_words2 = set(name2.split())
        common_name_words = name_words1.intersection(name_words2)
        
        # If more than 2 common words in names, likely similar
        if len(common_name_words) >= 2:
            return True
            
        # Check for common ingredients
        common_ingredients = ingredients1.intersection(ingredients2)
        if len(common_ingredients) >= 3:  # If 3 or more common ingredients
            return True
            
        # Check for specific patterns
        patterns = ['nugget', 'burger', 'sandwich', 'salad', 'pizza', 'pasta', 'rice', 'chicken', 'beef', 'fish']
        for pattern in patterns:
            if pattern in name1 and pattern in name2:
                return True
                
        return False

    def recommend_meal_plan(self, user_id, preferences, days=7):
        """Recommend a meal plan with 3 days of franchise meals and 4 days of dining hall meals"""
        # Define macro ranges based on goal
        goal = preferences.get('goal', 'maintain').lower()
        if goal == 'maintain':
            target_calories = 2250  # Middle of 2000-2500 range
            macro_ranges = {
                'protein': {'min': 0.20, 'max': 0.30},  # 20-30%
                'fat': {'min': 0.20, 'max': 0.35},      # 20-35%
                'carbs': {'min': 0.40, 'max': 0.50}     # 40-50%
            }
        elif goal == 'lose':
            target_calories = 1750  # Middle of 1500-2000 range
            macro_ranges = {
                'protein': {'min': 0.30, 'max': 0.40},  # 30-40%
                'fat': {'min': 0.20, 'max': 0.35},      # 20-35%
                'carbs': {'min': 0.45, 'max': 0.55}     # 45-55%
            }
        else:  # gain
            target_calories = 2750  # Middle of 2250-3250 range
            macro_ranges = {
                'protein': {'min': 0.25, 'max': 0.35},  # 25-35%
                'fat': {'min': 0.30, 'max': 0.40},      # 30-40%
                'carbs': {'min': 0.45, 'max': 0.55}     # 45-55%
            }

        # Define meal type calorie distribution
        meal_type_distribution = {
            'breakfast': 0.30,  # 30% of daily calories
            'lunch': 0.40,      # 40% of daily calories
            'dinner': 0.30      # 30% of daily calories
        }

        # Calculate target macros in grams for each meal type
        meal_type_targets = {}
        for meal_type, percentage in meal_type_distribution.items():
            meal_calories = target_calories * percentage
            meal_type_targets[meal_type] = {
                'calories': meal_calories,
                'protein': (meal_calories * macro_ranges['protein']['min']) / 4,  # 4 calories per gram
                'carbs': (meal_calories * macro_ranges['carbs']['min']) / 4,      # 4 calories per gram
                'fat': (meal_calories * macro_ranges['fat']['min']) / 9           # 9 calories per gram
            }

        meal_plan = []
        used_meals = set()
        used_restaurants = set()  # Track used restaurants for franchise days
        
        # Create 3 franchise days
        for day in range(3):
            day_meals = []
            meal_type_totals = {
                'breakfast': {'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0},
                'lunch': {'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0},
                'dinner': {'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0}
            }
            
            # Select franchise meals for each meal type
            for meal_type in ['breakfast', 'lunch', 'dinner']:
                targets = meal_type_targets[meal_type]
                current_totals = meal_type_totals[meal_type]
                
                # Get available franchise meals for this meal type
                available_meals = [m for m in self.meals 
                                 if m['mealId'] not in used_meals 
                                 and m['restaurantName'] not in used_restaurants
                                 and m['category'] == 'Franchise']
                
                if not available_meals:
                    # If no new restaurants available, allow previously used ones
                    available_meals = [m for m in self.meals 
                                     if m['mealId'] not in used_meals 
                                     and m['category'] == 'Franchise']
                
                if available_meals:
                    # Group meals by restaurant first
                    restaurant_groups = defaultdict(list)
                    for meal in available_meals:
                        restaurant_groups[meal['restaurantName']].append(meal)
                    
                    # Try to find a restaurant with enough meals for this meal type
                    selected_meals = []
                    selected_restaurant = None
                    
                    # Sort restaurants by number of available meals
                    sorted_restaurants = sorted(restaurant_groups.items(), 
                                             key=lambda x: len(x[1]), 
                                             reverse=True)
                    
                    for restaurant, meals in sorted_restaurants:
                        if len(meals) >= 3:  # Need at least 3 meals from this restaurant
                            # Sort meals by protein content for better macro balance
                            meals.sort(key=lambda x: x.get('protein', 0), reverse=True)
                            
                            for meal in meals:
                                if len(selected_meals) >= 3:
                                    break
                                    
                                # Check if this meal is similar to any already selected meal
                                if any(self.is_similar_item(meal, selected) for selected in selected_meals):
                                    continue
                                    
                                new_calories = current_totals['calories'] + meal.get('calories', 0)
                                if new_calories <= targets['calories'] * 1.1:  # Allow 10% over target
                                    meal['is_franchise'] = True
                                    meal['mealType'] = meal_type
                                    selected_meals.append(meal)
                                    used_meals.add(meal['mealId'])
                                    current_totals['calories'] = new_calories
                                    current_totals['protein'] += meal.get('protein', 0)
                                    current_totals['carbs'] += meal.get('carbohydrate', 0)
                                    current_totals['fat'] += meal.get('fat', 0)
                            
                            if selected_meals:
                                selected_restaurant = restaurant
                                break  # Found enough meals from one restaurant
                    
                    if selected_restaurant:
                        used_restaurants.add(selected_restaurant)
                    day_meals.extend(selected_meals)
            
            if day_meals:
                # Add category information to each meal
                for meal in day_meals:
                    meal['display_category'] = 'Franchise'
                
                # Group meals by type
                meals_by_type = {
                    'breakfast': [m for m in day_meals if m.get('mealType') == 'breakfast'],
                    'lunch': [m for m in day_meals if m.get('mealType') == 'lunch'],
                    'dinner': [m for m in day_meals if m.get('mealType') == 'dinner']
                }
                
                meal_plan.append({
                    'day': day + 1,
                    'meals_by_type': meals_by_type,
                    'category': 'Franchise'
                })
        
        # Create 4 dining hall days
        for day in range(4):
            day_meals = []
            meal_type_totals = {
                'breakfast': {'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0},
                'lunch': {'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0},
                'dinner': {'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0}
            }
            
            # Select dining hall meals for each meal type
            for meal_type in ['breakfast', 'lunch', 'dinner']:
                targets = meal_type_targets[meal_type]
                current_totals = meal_type_totals[meal_type]
                
                # Get available dining hall meals for this meal type
                available_meals = [m for m in self.meals 
                                 if m['mealId'] not in used_meals 
                                 and m['category'] == 'Dining-Halls']
                
                if available_meals:
                    # Group meals by dining hall (restaurant)
                    restaurant_groups = defaultdict(list)
                    for meal in available_meals:
                        restaurant_groups[meal['restaurantName']].append(meal)
                    
                    # Try to find a dining hall with enough meals for this meal type
                    selected_meals = []
                    for restaurant, meals in restaurant_groups.items():
                        if len(meals) >= 3:  # Need at least 3 meals from this dining hall
                            # Sort meals by protein content for better macro balance
                            meals.sort(key=lambda x: x.get('protein', 0), reverse=True)
                            
                            for meal in meals:
                                if len(selected_meals) >= 3:
                                    break
                                    
                                # Check if this meal is similar to any already selected meal
                                if any(self.is_similar_item(meal, selected) for selected in selected_meals):
                                    continue
                                    
                                new_calories = current_totals['calories'] + meal.get('calories', 0)
                                if new_calories <= targets['calories'] * 1.1:  # Allow 10% over target
                                    meal['is_franchise'] = False
                                    meal['mealType'] = meal_type
                                    selected_meals.append(meal)
                                    used_meals.add(meal['mealId'])
                                    current_totals['calories'] = new_calories
                                    current_totals['protein'] += meal.get('protein', 0)
                                    current_totals['carbs'] += meal.get('carbohydrate', 0)
                                    current_totals['fat'] += meal.get('fat', 0)
                            
                            if selected_meals:
                                break  # Found enough meals from one dining hall
                    
                    day_meals.extend(selected_meals)
            
            if day_meals:
                # Add category information to each meal
                for meal in day_meals:
                    meal['display_category'] = 'Dining Hall'
                
                # Group meals by type
                meals_by_type = {
                    'breakfast': [m for m in day_meals if m.get('mealType') == 'breakfast'],
                    'lunch': [m for m in day_meals if m.get('mealType') == 'lunch'],
                    'dinner': [m for m in day_meals if m.get('mealType') == 'dinner']
                }
                
                meal_plan.append({
                    'day': day + 4,  # Start from day 4 since first 3 days are franchise
                    'meals_by_type': meals_by_type,
                    'category': 'Dining Hall'
                })
        
        def validate_meal_combination(meals, targets):
            """Validate if a combination of meals meets macro requirements"""
            total_calories = sum(meal.get('calories', 0) for meal in meals)
            total_protein = sum(meal.get('protein', 0) for meal in meals)
            total_carbs = sum(meal.get('carbohydrate', 0) for meal in meals)
            total_fat = sum(meal.get('fat', 0) for meal in meals)

            if total_calories == 0:
                return False

            # Calculate macro percentages
            protein_percent = (total_protein * 4 / total_calories)
            carbs_percent = (total_carbs * 4 / total_calories)
            fat_percent = (total_fat * 9 / total_calories)

            # Check if within target ranges
            return (
                abs(total_calories - targets['calories']) <= targets['calories'] * 0.1 and  # Within 10% of target
                macro_ranges['protein']['min'] <= protein_percent <= macro_ranges['protein']['max'] and
                macro_ranges['carbs']['min'] <= carbs_percent <= macro_ranges['carbs']['max'] and
                macro_ranges['fat']['min'] <= fat_percent <= macro_ranges['fat']['max']
            )

        # Modify meal selection to consider macro requirements
        for day in meal_plan:
            for meal_type in ['breakfast', 'lunch', 'dinner']:
                if meal_type in day['meals_by_type']:
                    meals = day['meals_by_type'][meal_type]
                    targets = meal_type_targets[meal_type]
                    
                    # Try different combinations until we find one that meets requirements
                    from itertools import combinations
                    best_combination = None
                    best_score = float('-inf')
                    
                    for combo_size in range(1, min(4, len(meals) + 1)):
                        for combo in combinations(meals, combo_size):
                            if validate_meal_combination(combo, targets):
                                # Score based on how well it matches targets
                                total_calories = sum(meal.get('calories', 0) for meal in combo)
                                score = 1 - abs(total_calories - targets['calories']) / targets['calories']
                                
                                if score > best_score:
                                    best_score = score
                                    best_combination = combo
                    
                    if best_combination:
                        day['meals_by_type'][meal_type] = list(best_combination)

        return meal_plan
    
    def get_similar_meals(self, meal_id, num_similar=5):
        """Get similar meals based on content"""
        try:
            idx = next(i for i, meal in enumerate(self.meals) if meal['mealId'] == meal_id)
            similar_indices = self.similarity_matrix[idx].argsort()[-num_similar-1:-1][::-1]
            return [self.meals[i] for i in similar_indices]
        except StopIteration:
            return []

    def display_meal_plan(self, meal_plan):
        """Display the meal plan with macro information"""
        for day in meal_plan:
            day_num = day['day']
            category = day['category']
            print(f"\nDay {day_num} ({category})")
            print("-" * 30)
            
            daily_totals = {
                'calories': 0,
                'protein': 0,
                'carbs': 0,
                'fat': 0
            }
            
            for meal_type in ['breakfast', 'lunch', 'dinner']:
                if meal_type in day['meals_by_type'] and day['meals_by_type'][meal_type]:
                    meals = day['meals_by_type'][meal_type]
                    print(f"\n{meal_type.title()}:")
                    
                    meal_totals = {
                        'calories': 0,
                        'protein': 0,
                        'carbs': 0,
                        'fat': 0
                    }
                    
                    for meal in meals:
                        print(f"  - {meal['mealName']} ({meal['restaurantName']})")
                        print(f"    Calories: {meal.get('calories', 0)}")
                        print(f"    Protein: {meal.get('protein', 0)}g")
                        print(f"    Carbs: {meal.get('carbohydrate', 0)}g")
                        print(f"    Fat: {meal.get('fat', 0)}g")
                        
                        meal_totals['calories'] += meal.get('calories', 0)
                        meal_totals['protein'] += meal.get('protein', 0)
                        meal_totals['carbs'] += meal.get('carbohydrate', 0)
                        meal_totals['fat'] += meal.get('fat', 0)
                    
                    # Add to daily totals
                    daily_totals['calories'] += meal_totals['calories']
                    daily_totals['protein'] += meal_totals['protein']
                    daily_totals['carbs'] += meal_totals['carbs']
                    daily_totals['fat'] += meal_totals['fat']
                    
                    # Display meal type totals and percentages
                    if meal_totals['calories'] > 0:
                        print(f"\n  {meal_type.title()} Totals:")
                        print(f"  Calories: {meal_totals['calories']}")
                        print(f"  Protein: {meal_totals['protein']}g ({(meal_totals['protein'] * 4 / meal_totals['calories']) * 100:.1f}%)")
                        print(f"  Carbs: {meal_totals['carbs']}g ({(meal_totals['carbs'] * 4 / meal_totals['calories']) * 100:.1f}%)")
                        print(f"  Fat: {meal_totals['fat']}g ({(meal_totals['fat'] * 9 / meal_totals['calories']) * 100:.1f}%)")
            
            # Display daily totals and percentages
            if daily_totals['calories'] > 0:
                print("\nDaily Totals:")
                print(f"Calories: {daily_totals['calories']}")
                print(f"Protein: {daily_totals['protein']}g ({(daily_totals['protein'] * 4 / daily_totals['calories']) * 100:.1f}%)")
                print(f"Carbs: {daily_totals['carbs']}g ({(daily_totals['carbs'] * 4 / daily_totals['calories']) * 100:.1f}%)")
                print(f"Fat: {daily_totals['fat']}g ({(daily_totals['fat'] * 9 / daily_totals['calories']) * 100:.1f}%)")