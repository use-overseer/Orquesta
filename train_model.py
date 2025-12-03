import joblib
import numpy as np
from sklearn.linear_model import LinearRegression

# Create a simple dummy model
# Input: [role_index, age, experience_years, available]
# Output: score

# Training data (dummy)
X = np.array([
    [1, 25, 2, 1],
    [1, 30, 5, 1],
    [1, 40, 10, 1],
    [1, 20, 0, 0], # Unavailable
    [2, 25, 2, 1],
    [2, 35, 8, 1],
])

# Target scores (higher is better)
y = np.array([
    0.5,
    0.7,
    0.9,
    0.0,
    0.5,
    0.8
])

model = LinearRegression()
model.fit(X, y)

# Save the model
joblib.dump(model, "ml_model.pkl")
print("Model trained and saved to ml_model.pkl")
