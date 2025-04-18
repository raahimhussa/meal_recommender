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
            
            # Ensure all meals have required fields
            for meal in self.meals:
                meal['mealName'] = meal.get('mealName', 'Unnamed Meal')
                meal['restaurantName'] = meal.get('restaurantName', 'Unknown Restaurant')
                meal['calories'] = float(meal.get('calories', 0))
                meal['protein'] = float(meal.get('protein', 0))
                meal['carbohydrate'] = float(meal.get('carbohydrate', 0))
                meal['fat'] = float(meal.get('fat', 0))
                meal['mealType'] = meal.get('mealType', 'Unknown')
                
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
        
        # Define nutrition ranges based on goal
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
            if portioned_meal['calories'] > target_calories_per_meal * 0.9:  # Allow meals up to 90% of target
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
            
            # Score based on macro percentages (more lenient)
            macro_score = 0
            if (macro_ranges['protein']['min'] * 0.8 <= protein_percent <= macro_ranges['protein']['max'] * 1.2 and
                macro_ranges['carbs']['min'] * 0.8 <= carbs_percent <= macro_ranges['carbs']['max'] * 1.2 and
                macro_ranges['fat']['min'] * 0.8 <= fat_percent <= macro_ranges['fat']['max'] * 1.2):
                macro_score = 1.0
            else:
                # Calculate how far from target ranges (more lenient)
                protein_diff = min(
                    abs(protein_percent - macro_ranges['protein']['min'] * 0.8),
                    abs(protein_percent - macro_ranges['protein']['max'] * 1.2)
                )
                carbs_diff = min(
                    abs(carbs_percent - macro_ranges['carbs']['min'] * 0.8),
                    abs(carbs_percent - macro_ranges['carbs']['max'] * 1.2)
                )
                fat_diff = min(
                    abs(fat_percent - macro_ranges['fat']['min'] * 0.8),
                    abs(fat_percent - macro_ranges['fat']['max'] * 1.2)
                )
                macro_score = 1 - (protein_diff + carbs_diff + fat_diff) / 3
            
            # Score based on calorie match (more lenient)
            ideal_portion = target_calories_per_meal * 0.3  # Target 30% of meal calories
            calorie_score = 1 - min(abs(meal_calories - ideal_portion) / (ideal_portion * 2), 1)  # Even more lenient
            
            # Add random factor for variety
            random_factor = random.uniform(0.8, 1.2)
            
            # Calculate overall score with random factor
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
                # Randomly select from top 100 meals for variety
                top_meals = time_filtered_meals[:100]
                random.shuffle(top_meals)
                
                combinations_tried = 0
                valid_combinations = 0
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
                        combinations_tried += 1
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
                        
                        # Skip combinations that exceed calorie limit (more lenient)
                        if total_calories > target_calories_per_meal * 1.5:  # Allow 50% flexibility
                            continue
                        
                        # Skip combinations that are too low in calories (more lenient)
                        if total_calories < target_calories_per_meal * 0.5:  # Require at least 50% of target
                            continue
                        
                        # Calculate macro percentages for the combination
                        protein_percent = (total_macros['protein'] * 4 / total_calories)
                        carbs_percent = (total_macros['carbs'] * 4 / total_calories)
                        fat_percent = (total_macros['fat'] * 9 / total_calories)
                        
                        # Score based on macro percentages (more lenient)
                        macro_score = 0
                        if (macro_ranges['protein']['min'] * 0.7 <= protein_percent <= macro_ranges['protein']['max'] * 1.3 and
                            macro_ranges['carbs']['min'] * 0.7 <= carbs_percent <= macro_ranges['carbs']['max'] * 1.3 and
                            macro_ranges['fat']['min'] * 0.7 <= fat_percent <= macro_ranges['fat']['max'] * 1.3):
                            macro_score = 1.0
                        else:
                            # Calculate how far from target ranges (more lenient)
                            protein_diff = min(
                                abs(protein_percent - macro_ranges['protein']['min'] * 0.7),
                                abs(protein_percent - macro_ranges['protein']['max'] * 1.3)
                            )
                            carbs_diff = min(
                                abs(carbs_percent - macro_ranges['carbs']['min'] * 0.7),
                                abs(carbs_percent - macro_ranges['carbs']['max'] * 1.3)
                            )
                            fat_diff = min(
                                abs(fat_percent - macro_ranges['fat']['min'] * 0.7),
                                abs(fat_percent - macro_ranges['fat']['max'] * 1.3)
                            )
                            macro_score = 1 - (protein_diff + carbs_diff + fat_diff) / 3
                        
                        # Score based on calorie match (more lenient)
                        calorie_score = 1 - min(abs(total_calories - target_calories_per_meal) / (target_calories_per_meal * 2.5), 1)
                        
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
                            valid_combinations += 1
            
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
            for meal in day['meals']:
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
        total_meals = sum(len(day['meals']) for day in meal_plan)
        swipe_limit = preferences.get('swipe_limit', 19)
        if total_meals > swipe_limit:
            validation_results['swipes'] = False
            validation_results['messages'].append(
                f"Total meals ({total_meals}) exceed swipe limit ({swipe_limit})"
            )
        
        return validation_results
    
    def recommend_meal_plan(self, user_id, preferences, days=7):
        """
        Recommend a weekly meal plan with guaranteed variety and validation
        """
        meal_plan = []
        used_restaurants = set()
        used_meals = set()
        
        for day in range(days):
            # Get recommendations excluding used restaurants
            temp_prefs = preferences.copy()
            temp_prefs['exclude_restaurants'] = list(used_restaurants)
            
            # Get daily meals with retries
            daily_meals = []
            remaining_attempts = 10
            
            while remaining_attempts > 0 and len(daily_meals) < 3:
                recommendations = self.get_recommendations(user_id, temp_prefs, 5)
                
                for meal in recommendations:
                    if (meal['mealId'] not in used_meals and 
                        meal['restaurantName'] not in used_restaurants):
                        daily_meals.append(meal)
                        used_meals.add(meal['mealId'])
                        used_restaurants.add(meal['restaurantName'])
                        break
                
                remaining_attempts -= 1
            
            if daily_meals:
                meal_plan.append({
                    'day': day + 1,
                    'restaurant': daily_meals[0]['restaurantName'],
                    'meals': daily_meals
                })
        
        # Validate the meal plan
        validation = self.validate_meal_plan(meal_plan, preferences)
        if not all(validation.values()):
            print("\nMeal Plan Validation Warnings:")
            for message in validation['messages']:
                print(f"- {message}")
        
        return meal_plan
    
    def get_similar_meals(self, meal_id, num_similar=5):
        """Get similar meals based on content"""
        try:
            idx = next(i for i, meal in enumerate(self.meals) if meal['mealId'] == meal_id)
            similar_indices = self.similarity_matrix[idx].argsort()[-num_similar-1:-1][::-1]
            return [self.meals[i] for i in similar_indices]
        except StopIteration:
            return []