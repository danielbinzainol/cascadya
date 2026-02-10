import pandas as pd
import numpy as np
from scipy.stats import norm




def predict_model(model, X):
    y = pd.Series(model.predict(X), index=X.index)
    return y

def a_priori_knowledge(y):
     y = np.maximum(0., y)
     return y

######### 95% confidence interval
def pred_interval(prediction,y_test,y_fore,alpha=0.95):
    """
    Obtain the prediction interval for each of the prediction
    Input: single prediction, entire test data, test set predictions
    Output: Prediction intervals and the actual prediction
    """
    y_fore = np.array(y_fore)

    # Calculate the sum of squares of the residuals
    err = np.sum(np.square((y_test - y_fore)))

    # Estimate the standard error 
    std = np.sqrt((1 / (y_test.shape[0] - 2)) * err) ## why -2?

    # Compute the z-score
    z = norm.ppf(1 - (1-alpha)/2) # 1.96 for alpha=0.95

    # Calculate the interval
    interval = z*std
    return [prediction-interval,prediction,prediction+interval] 

def confidence_interval(y_test, y_fore):
    prediction_interval = []
    for i in range(y_test.shape[0]):
        prediction_interval.append(pred_interval(y_fore.iloc[i],y_test,y_fore))
    pred_int = pd.DataFrame(prediction_interval,columns=['Lower','Actual','Upper']) 
    return pred_int

