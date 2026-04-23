from cascadya_features.server import create_app, launch_server


app = create_app()


if __name__ == "__main__":
    launch_server(app)
