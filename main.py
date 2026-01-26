from sklearn.model_selection import TimeSeriesSplit, cross_val_predict

#
from steps.ingest import data_workflow
from steps.train import model_choice, create_feature, train_model
from steps.predict import predict_model, a_priori_knowledge, confidence_interval
from steps.evaluate import evaluate_model, cv_evaluate
from plots import plot_timeseries_csv, plot_weekday_seasonal_csv, simple_lag_plot, cool_plot

def plot_workflow(y):
    plot_timeseries_csv(y)
    plot_weekday_seasonal_csv(y)

### Simple regression on lag of 1 hour ###
def simple_lag(steam_cons):
    # simple lag
    steam_cons['Lag_1'] = steam_cons['MWh use'].shift(1)
    steam_cons.head()    


    X = steam_cons.loc[:, ['Lag_1']]
    X.dropna(inplace=True)  # drop missing values in the feature set
    y = steam_cons.loc[:, 'MWh use']  # create the target
    y, X = y.align(X, join='inner')  # drop corresponding values in target

    model = model_choice("LinearRegression")
    train_model(model, X, y)

    y_pred = predict_model(model, X)

    simple_lag_plot(X, y, y_pred)


def fit_pred_fore_priori_plot_workflow(model, X_train, X_test):
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

##############################
if __name__ == "__main__":
    y = data_workflow("france_champignon")
    # give information on the frequency of the index:
    
    # target
    # y = steam_cons["MWh use"] # the target ## faudrait garder ??

    X = create_feature(y)

    y = y.loc[X.index] # because X is now shorter, as we dropped the lines with at least a NaN. 168 hours lag, so we lose a week.


    # instanciate the model
    model = model_choice("LinearRegression")

    ######## CV workflow ########
    ########## split training and test sets #######
    ts_cv = TimeSeriesSplit(
        n_splits=6, # 6 weeks?
        # gap=24, # assume unavailable data for 24 hours ? Je ne comprends pour l'instant comment avoir un gap de 1 jour et utiliser un lag de 1h
        test_size=7*24,
    )

    all_splits = list(ts_cv.split(X, y))

    # predict and plot for each fold
    for ind, el in enumerate(all_splits):
        train_split, test_split = all_splits[ind]
        X_train = X.iloc[train_split]
        X_test = X.iloc[test_split]

        fit_pred_fore_priori_plot_workflow(model, X_train, X_test)

    # evaluate model through cross-validation for time series
    cv_results = cv_evaluate(model, X, y, ts_cv=ts_cv, model_prop="n_features_in_")

    # ######## simple 80/20 split workflow
    # # naive 80/20 approach, splitting in November
    # X_train = X[X.index < "2024-11-01"]
    # X_test = X[X.index >= "2024-11-01"]

    # y_test, y_fore = fit_pred_fore_priori_plot_workflow(model, X_train, X_test)
    # rmse = evaluate_model(y_test, y_fore)