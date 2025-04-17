import json
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict
import random
from datetime import datetime
from itertools import combinations

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
        self.user_history = defaultdict(set)  # Track user meal history
        
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
    
    def get_recommendations(self, user_id, preferences, num_recommendations=3):
        """Get personalized meal recommendations based on weight goal and nutrition requirements"""
        # Load user history
        self.load_history(user_id)
        
        # Get meal time from preferences
        meal_time = preferences.get('meal_time', 'breakfast')
        
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
        
        # Calculate target macros in grams
        target_macros = {
            'protein': {
                'min': (target_calories * macro_ranges['protein']['min']) / 4,  # 4 calories per gram
                'max': (target_calories * macro_ranges['protein']['max']) / 4
            },
            'carbs': {
                'min': (target_calories * macro_ranges['carbs']['min']) / 4,    # 4 calories per gram
                'max': (target_calories * macro_ranges['carbs']['max']) / 4
            },
            'fat': {
                'min': (target_calories * macro_ranges['fat']['min']) / 9,      # 9 calories per gram
                'max': (target_calories * macro_ranges['fat']['max']) / 9
            }
        }
        
        # Filter meals based on preferences and meal time
        filtered_meals = []
        for meal in self.meals:
            # Skip meals that don't match meal time
            if meal_time.lower() not in meal.get('mealType', '').lower():
                continue
                
            # Skip meals with no nutrition data
            if not meal.get('calories') or not meal.get('protein') or not meal.get('carbohydrate') or not meal.get('fat'):
                continue
                
            filtered_meals.append(meal)
        
        if not filtered_meals:
            print(f"No meals found for {meal_time}. Trying all meals...")
            filtered_meals = self.meals
        
        # Calculate target per meal
        target_calories_per_meal = target_calories / num_recommendations
        target_macros_per_meal = {
            'protein': {
                'min': target_macros['protein']['min'] / num_recommendations,
                'max': target_macros['protein']['max'] / num_recommendations
            },
            'carbs': {
                'min': target_macros['carbs']['min'] / num_recommendations,
                'max': target_macros['carbs']['max'] / num_recommendations
            },
            'fat': {
                'min': target_macros['fat']['min'] / num_recommendations,
                'max': target_macros['fat']['max'] / num_recommendations
            }
        }
        
        # Score meals based on how well they match the target ranges
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
            
            # Score based on macro percentages (within target ranges)
            macro_score = 0
            if (macro_ranges['protein']['min'] <= protein_percent <= macro_ranges['protein']['max'] and
                macro_ranges['carbs']['min'] <= carbs_percent <= macro_ranges['carbs']['max'] and
                macro_ranges['fat']['min'] <= fat_percent <= macro_ranges['fat']['max']):
                macro_score = 1.0
            else:
                # Calculate how far from target ranges
                protein_diff = min(
                    abs(protein_percent - macro_ranges['protein']['min']),
                    abs(protein_percent - macro_ranges['protein']['max'])
                )
                carbs_diff = min(
                    abs(carbs_percent - macro_ranges['carbs']['min']),
                    abs(carbs_percent - macro_ranges['carbs']['max'])
                )
                fat_diff = min(
                    abs(fat_percent - macro_ranges['fat']['min']),
                    abs(fat_percent - macro_ranges['fat']['max'])
                )
                macro_score = 1 - (protein_diff + carbs_diff + fat_diff) / 3
            
            # Score based on calorie match
            calorie_score = 1 - min(abs(meal_calories - target_calories_per_meal) / target_calories_per_meal, 1)
            
            # Calculate overall score (70% macro match, 30% calorie match)
            overall_score = (macro_score * 0.7 + calorie_score * 0.3)
            
            scored_meals.append((overall_score, meal))
        
        # Sort by score
        scored_meals.sort(reverse=True, key=lambda x: x[0])
        
        # Find the best combination of meals
        best_combination = None
        best_total_score = float('-inf')
        best_total_match = float('-inf')
        
        # Try different combinations of the top scoring meals
        top_meals = scored_meals[:200]  # Consider more meals for better combinations
        for meal_combination in combinations(top_meals, num_recommendations):
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
            
            # Calculate macro percentages for the combination
            protein_percent = (total_macros['protein'] * 4 / total_calories)
            carbs_percent = (total_macros['carbs'] * 4 / total_calories)
            fat_percent = (total_macros['fat'] * 9 / total_calories)
            
            # Score based on macro percentages
            macro_score = 0
            if (macro_ranges['protein']['min'] <= protein_percent <= macro_ranges['protein']['max'] and
                macro_ranges['carbs']['min'] <= carbs_percent <= macro_ranges['carbs']['max'] and
                macro_ranges['fat']['min'] <= fat_percent <= macro_ranges['fat']['max']):
                macro_score = 1.0
            else:
                # Calculate how far from target ranges
                protein_diff = min(
                    abs(protein_percent - macro_ranges['protein']['min']),
                    abs(protein_percent - macro_ranges['protein']['max'])
                )
                carbs_diff = min(
                    abs(carbs_percent - macro_ranges['carbs']['min']),
                    abs(carbs_percent - macro_ranges['carbs']['max'])
                )
                fat_diff = min(
                    abs(fat_percent - macro_ranges['fat']['min']),
                    abs(fat_percent - macro_ranges['fat']['max'])
                )
                macro_score = 1 - (protein_diff + carbs_diff + fat_diff) / 3
            
            # Score based on calorie match
            calorie_score = 1 - min(abs(total_calories - target_calories) / target_calories, 1)
            
            # Calculate total match score
            total_match_score = (macro_score * 0.7 + calorie_score * 0.3)
            
            # Calculate combination score (weighted average of individual scores and total match)
            individual_scores = sum(score for score, _ in meal_combination) / num_recommendations
            combination_score = (total_match_score * 0.8 + individual_scores * 0.2)
            
            # Always update best combination if we find a better score
            if combination_score > best_total_score:
                best_total_score = combination_score
                best_total_match = total_match_score
                best_combination = meal_combination
        
        # Always return the best combination we found, even if it doesn't meet all requirements
        if best_combination:
            recommendations = [meal for _, meal in best_combination]
            
            # Calculate final totals
            final_calories = sum(meal.get('calories', 0) for meal in recommendations)
            final_protein = sum(meal.get('protein', 0) for meal in recommendations)
            final_carbs = sum(meal.get('carbohydrate', 0) for meal in recommendations)
            final_fat = sum(meal.get('fat', 0) for meal in recommendations)
            
            # Calculate final macro percentages
            final_protein_percent = (final_protein * 4 / final_calories) * 100
            final_carbs_percent = (final_carbs * 4 / final_calories) * 100
            final_fat_percent = (final_fat * 9 / final_calories) * 100
            
            # Add match quality information to the first meal
            recommendations[0]['match_quality'] = {
                'calories': f"{final_calories}/{target_calories} ({((final_calories/target_calories)*100):.1f}%)",
                'protein': f"{final_protein}g ({final_protein_percent:.1f}%)",
                'carbs': f"{final_carbs}g ({final_carbs_percent:.1f}%)",
                'fat': f"{final_fat}g ({final_fat_percent:.1f}%)",
                'goal': goal.capitalize(),
                'target_ranges': {
                    'protein': f"{macro_ranges['protein']['min']*100:.0f}-{macro_ranges['protein']['max']*100:.0f}%",
                    'carbs': f"{macro_ranges['carbs']['min']*100:.0f}-{macro_ranges['carbs']['max']*100:.0f}%",
                    'fat': f"{macro_ranges['fat']['min']*100:.0f}-{macro_ranges['fat']['max']*100:.0f}%"
                },
                'overall_match': f"{best_total_match*100:.1f}%"
            }
            
            # Update and save history
            for meal in recommendations:
                self.user_history[user_id].add(meal['mealId'])
            self.save_history(user_id)
            
            return recommendations
        
        # If we still don't have a combination, return the top individual meals
        if scored_meals:
            recommendations = [meal for _, meal in scored_meals[:num_recommendations]]
            
            # Calculate final totals
            final_calories = sum(meal.get('calories', 0) for meal in recommendations)
            final_protein = sum(meal.get('protein', 0) for meal in recommendations)
            final_carbs = sum(meal.get('carbohydrate', 0) for meal in recommendations)
            final_fat = sum(meal.get('fat', 0) for meal in recommendations)
            
            # Calculate final macro percentages
            final_protein_percent = (final_protein * 4 / final_calories) * 100
            final_carbs_percent = (final_carbs * 4 / final_calories) * 100
            final_fat_percent = (final_fat * 9 / final_calories) * 100
            
            # Add match quality information to the first meal
            recommendations[0]['match_quality'] = {
                'calories': f"{final_calories}/{target_calories} ({((final_calories/target_calories)*100):.1f}%)",
                'protein': f"{final_protein}g ({final_protein_percent:.1f}%)",
                'carbs': f"{final_carbs}g ({final_carbs_percent:.1f}%)",
                'fat': f"{final_fat}g ({final_fat_percent:.1f}%)",
                'goal': goal.capitalize(),
                'target_ranges': {
                    'protein': f"{macro_ranges['protein']['min']*100:.0f}-{macro_ranges['protein']['max']*100:.0f}%",
                    'carbs': f"{macro_ranges['carbs']['min']*100:.0f}-{macro_ranges['carbs']['max']*100:.0f}%",
                    'fat': f"{macro_ranges['fat']['min']*100:.0f}-{macro_ranges['fat']['max']*100:.0f}%"
                },
                'overall_match': "Best available match"
            }
        
        # Update and save history
        for meal in recommendations:
            self.user_history[user_id].add(meal['mealId'])
        self.save_history(user_id)
        
        return recommendations
    
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