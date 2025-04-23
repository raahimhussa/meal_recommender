const axios = require('axios');

const FLASK_API_URL = 'http://localhost:5000/api/recommend';

async function getMealRecommendations(userPreferences) {
    try {
        const response = await axios.post(FLASK_API_URL, {
            user_id: userPreferences.userId,
            goal: userPreferences.goal,
            target_calories: userPreferences.targetCalories,
            allergies: userPreferences.allergies || [],
            exercise: userPreferences.exercise || 'Regular exercise',
            preferred_locations: userPreferences.preferredLocations || [],
            novelty_factor: userPreferences.noveltyFactor || 0.5,
            dietary_restrictions: userPreferences.dietaryRestrictions || [],
            selected_meals: userPreferences.selectedMeals || ['breakfast', 'lunch', 'dinner']
        });

        if (response.data.success) {
            return {
                success: true,
                mealPlan: response.data.meal_plan
            };
        } else {
            throw new Error(response.data.error);
        }
    } catch (error) {
        console.error('Error getting meal recommendations:', error);
        return {
            success: false,
            error: error.message
        };
    }
}

module.exports = {
    getMealRecommendations
}; 