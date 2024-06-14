from stravalib import Client
import json
import time
import gzip
import io


def load_secrets(file_path):
    with open(file_path, "r") as file:
        secrets = json.load(file)
    return secrets


def update_secrets(file_path, new_secrets):
    with open(file_path, "w") as file:
        json.dump(new_secrets, file, indent=2)


def check_and_refresh_access_token(secrets_file):
    secrets = load_secrets(secrets_file)
    client = Client()

    # Check if the access token has expired
    if secrets["strava"]["token_expires_at"] < time.time():
        # Refresh the access token
        refresh_response = client.refresh_access_token(
            client_id=secrets["strava"]["client_id"],
            client_secret=secrets["strava"]["client_secret"],
            refresh_token=secrets["strava"]["refresh_token"],
        )

        # Update the secrets with the new tokens and expiration
        secrets["strava"]["access_token"] = refresh_response["access_token"]
        secrets["strava"]["refresh_token"] = refresh_response["refresh_token"]
        secrets["strava"]["token_expires_at"] = refresh_response["expires_at"]

        # Write the updated secrets back to the file
        update_secrets(secrets_file, secrets)

        print("Access token refreshed and secrets file updated.")
        return secrets
    else:
        print("Access token is still valid.")
        return secrets


# Initialize the Strava client
# secrets = load_secrets("config/secrets.json")

secrets = check_and_refresh_access_token(
    secrets_file="config/secrets.json",
)
print(secrets)

client = Client(access_token=secrets["strava"]["access_token"])
athlete = client.get_athlete()
athlete_id = athlete.id

stats = client.get_athlete_stats(athlete_id)
print(stats)

with open(file="data/mywellness_45m_20240614.tcx", mode="rb") as f:
    file_content = f.read()

compressed_content = io.BytesIO()
with gzip.GzipFile(fileobj=compressed_content, mode="wb") as gzip_file:
    gzip_file.write(file_content)

compressed_content.seek(0)
compressed_bytes_io = io.BytesIO(compressed_content.read())

upload = client.upload_activity(
    activity_file=compressed_bytes_io,
    data_type="tcx.gz",
    name="PTR010 - 45m effort",
    description="Technogym",
    activity_type="ride",
    private=False,
    external_id="",
    trainer=True,
    commute=False,
)
