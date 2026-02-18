from train import model_choice, train_model
from predict import predict_model, a_priori_knowledge, confidence_interval
from plots import simple_lag_plot, cool_plot


### Simple regression on lag of 1 hour ###
def simple_lag(y, value_col):
    # simple lag
    y['Lag_1'] = y[value_col].shift(1)
    y.head()    


    X = y.loc[:, ['Lag_1']]
    X.dropna(inplace=True)  # drop missing values in the feature set
    y = y.loc[:, value_col]  # create the target
    y, X = y.align(X, join='inner')  # drop corresponding values in target

    model = model_choice("LinearRegression")
    train_model(model, X, y)

    y_pred = predict_model(model, X)

    simple_lag_plot(X, y, y_pred)


def fit_pred_fore_priori_plot_workflow(model, y, X_train, X_test):
        y_train = y.loc[X_train.index]
        y_test = y.loc[X_test.index]

        train_model(model, X_train, y_train)

        y_pred = predict_model(model, X_train)
        y_pred = a_priori_knowledge(y_pred)

        y_fore = predict_model(model, X_test)
        y_fore = a_priori_knowledge(y_fore)

        pred_int = confidence_interval(y_test, y_fore)
        cool_plot(y, y_fore, pred_int, y_pred)

        return y_test, y_fore
