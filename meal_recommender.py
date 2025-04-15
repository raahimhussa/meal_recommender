import json
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict
import random
from datetime import datetime

class MealRecommender:
    def __init__(self, json_file):
        self.load_data(json_file)
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
        for meal in self.data:
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
        feature_strings = [meal['feature_string'] for meal in self.data]
        self.tfidf_matrix = self.vectorizer.fit_transform(feature_strings)
        
        # Calculate similarity matrix
        self.similarity_matrix = cosine_similarity(self.tfidf_matrix)
    
    def get_recommendations(self, user_id, preferences, num_recommendations=3):
        """
        Get personalized meal recommendations with variety
        """
        # Load user history
        self.load_history(user_id)
        
        # Filter meals based on preferences
        filtered_meals = self.filter_meals(preferences)
        
        if not filtered_meals:
            return []
        
        # Get target calories
        target_calories = preferences.get('target_calories', 1000)
        
        # Group meals by restaurant
        restaurant_meals = defaultdict(list)
        for meal in filtered_meals:
            restaurant_meals[meal['restaurantName']].append(meal)
        
        # Choose a random restaurant that has enough meals
        valid_restaurants = [r for r, meals in restaurant_meals.items() if len(meals) >= num_recommendations]
        if not valid_restaurants:
            return []
        
        # Use user_id to seed the random selection for consistency
        random.seed(hash(user_id))
        selected_restaurant = random.choice(valid_restaurants)
        random.seed()  # Reset random seed
        
        restaurant_meals = restaurant_meals[selected_restaurant]
        
        # Score meals with user-specific factors
        scored_meals = []
        for meal in restaurant_meals:
            # Skip meals that user has had before
            if meal['mealId'] in self.user_history[user_id]:
                continue
            score = self.score_meal(meal, preferences, self.user_history[user_id], user_id)
            scored_meals.append((score, meal))
        
        # Sort by score
        scored_meals.sort(reverse=True, key=lambda x: x[0])
        
        # Select meals to reach target calories
        recommendations = []
        current_calories = 0
        remaining_calories = target_calories
        
        for score, meal in scored_meals:
            meal_calories = meal.get('calories', 0)
            
            # If adding this meal won't exceed target calories
            if current_calories + meal_calories <= target_calories:
                recommendations.append(meal)
                current_calories += meal_calories
                remaining_calories = target_calories - current_calories
                
                # If we've reached target calories, stop
                if remaining_calories <= 0:
                    break
                
                # If we still need more calories, continue adding meals
                if len(recommendations) < num_recommendations:
                    continue
                else:
                    break
        
        # If we still have remaining calories and haven't reached max recommendations,
        # try to find a smaller meal to add
        if remaining_calories > 0 and len(recommendations) < num_recommendations:
            for score, meal in scored_meals:
                if meal in recommendations:
                    continue
                    
                meal_calories = meal.get('calories', 0)
                if meal_calories <= remaining_calories:
                    recommendations.append(meal)
                    current_calories += meal_calories
                    break
        
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
        target_calories = preferences.get('target_calories', 0)
        macros = preferences.get('macros', {})
        
        print(f"\nFiltering meals for {meal_time}...")
        print(f"Target calories: {target_calories}")
        print(f"Target macros: {macros}")
        
        for meal in self.data:
            # Check if restaurant is in preferred locations
            restaurant_name = meal['restaurantName'].lower()
            if preferred_locations and not any(loc.lower() in restaurant_name for loc in preferred_locations):
                continue
                
            # Check dietary restrictions
            if dietary_restrictions:
                meal_tags = meal.get('tags', [])
                meal_tags = [tag.lower() for tag in meal_tags]
                restrictions = [r.lower() for r in dietary_restrictions]
                
                has_conflict = False
                for restriction in restrictions:
                    if restriction.startswith('no '):
                        restricted_item = restriction[3:]
                        if restricted_item in meal_tags:
                            has_conflict = True
                            break
                    elif restriction not in meal_tags:
                        conflicting_tags = {
                            'vegetarian': ['meat', 'chicken', 'beef', 'pork', 'fish'],
                            'vegan': ['meat', 'chicken', 'beef', 'pork', 'fish', 'dairy', 'eggs', 'cheese'],
                            'gluten-free': ['wheat', 'gluten'],
                            'dairy-free': ['dairy', 'cheese', 'milk']
                        }
                        if restriction in conflicting_tags:
                            for conflict in conflicting_tags[restriction]:
                                if conflict in meal_tags:
                                    has_conflict = True
                                    break
                
                if has_conflict:
                    continue
                
            # Check allergens
            if any(allergen in meal.get('allergens', []) for allergen in preferences.get('allergies', [])):
                continue
            
            filtered.append(meal)
        
        return filtered
    
    def score_meal(self, meal, preferences, user_history, user_id):
        """Score a meal with user-specific factors"""
        score = 0
        
        # Calorie-based scoring (40% weight)
        target_calories = preferences.get('target_calories', 0)
        meal_calories = meal.get('calories', 0)
        
        if target_calories > 0:
            calorie_diff = abs(meal_calories - target_calories)
            calorie_score = 1 - min(calorie_diff / target_calories, 1)
            score += calorie_score * 0.4
        
        # Macro-based scoring (30% weight)
        macros = preferences.get('macros', {})
        if macros:
            macro_scores = []
            
            # Protein scoring
            if 'protein' in macros:
                target_protein = macros['protein']
                meal_protein = meal.get('protein', 0)
                if target_protein > 0:
                    protein_score = 1 - min(abs(meal_protein - target_protein) / target_protein, 1)
                    macro_scores.append(protein_score)
            
            # Carbs scoring
            if 'carbs' in macros:
                target_carbs = macros['carbs']
                meal_carbs = meal.get('carbohydrate', 0)
                if target_carbs > 0:
                    carbs_score = 1 - min(abs(meal_carbs - target_carbs) / target_carbs, 1)
                    macro_scores.append(carbs_score)
            
            # Fat scoring
            if 'fat' in macros:
                target_fat = macros['fat']
                meal_fat = meal.get('fat', 0)
                if target_fat > 0:
                    fat_score = 1 - min(abs(meal_fat - target_fat) / target_fat, 1)
                    macro_scores.append(fat_score)
            
            if macro_scores:
                macro_score = sum(macro_scores) / len(macro_scores)
                score += macro_score * 0.3
        
        # Restaurant category scoring (20% weight)
        meal_time = preferences.get('meal_time', 'breakfast')
        restaurant_name = meal['restaurantName'].lower()
        preferred_locations = preferences.get('preferred_locations', [])
        
        if any(loc.lower() in restaurant_name for loc in preferred_locations):
            score += 0.2
        
        # Novelty factor (10% weight)
        novelty_factor = preferences.get('novelty_factor', 0.5)
        if meal['mealId'] not in user_history:
            score += 0.1 * novelty_factor
        
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
            idx = next(i for i, meal in enumerate(self.data) if meal['mealId'] == meal_id)
            similar_indices = self.similarity_matrix[idx].argsort()[-num_similar-1:-1][::-1]
            return [self.data[i] for i in similar_indices]
        except StopIteration:
            return []