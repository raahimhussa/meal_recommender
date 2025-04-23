const express = require('express');
const router = express.Router();
const { getMealRecommendations } = require('./mealRecommender');

router.post('/recommend', async (req, res) => {
    try {
        const userPreferences = req.body;
        
        if (!userPreferences.userId || !userPreferences.goal || !userPreferences.targetCalories) {
            return res.status(400).json({
                success: false,
                error: 'Missing required fields: userId, goal, and targetCalories are required'
            });
        }

        const result = await getMealRecommendations(userPreferences);
        
        if (result.success) {
            res.json({
                success: true,
                mealPlan: result.mealPlan
            });
        } else {
            res.status(500).json({
                success: false,
                error: result.error
            });
        }
    } catch (error) {
        console.error('Error in meal recommendation route:', error);
        res.status(500).json({
            success: false,
            error: 'Internal server error'
        });
    }
});

module.exports = router; 