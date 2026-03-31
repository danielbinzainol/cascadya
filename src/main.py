from sklearn.model_selection import TimeSeriesSplit

#
from src.ingest import data_workflow
from src.dataset import analyze, detect_elapsed_time_anomalies, resample
from src.train import model_choice, create_feature
from src.evaluate import cv_evaluate
from src.autres import fit_pred_fore_priori_plot_workflow
from plots import plot_timeseries


def main():
    df = data_workflow("inariz")
    analyze(df)
    elapsed_anomalies, expected_delta = detect_elapsed_time_anomalies(df, timestamp_col="measured_at_utc")
    # target
    y = df[["measured_at_utc", "steam_consumption_m3_h"]]
    y_10min = resample(y, desired_timedelta="10min", aggregate_function="mean") # TODO vérfiier comment se fait ce mean, pas sur que je sois content, mieux vaut peut etre prendre le point le plus proche
    plot_timeseries(y_10min.set_index("measured_at_utc"))

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


if __name__ == "__main__":
    main()    