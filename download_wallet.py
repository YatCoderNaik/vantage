import os
import zipfile
import io
from google.cloud import secretmanager

def prepare_wallet():
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        print("GOOGLE_CLOUD_PROJECT not set. Skipping wallet download.")
        return

    client = secretmanager.SecretManagerServiceClient()
    secret_name = f"projects/{project_id}/secrets/oracle-vantage-wallet-zip/versions/latest"
    
    try:
        print(f"Downloading wallet zip from {secret_name}...")
        response = client.access_secret_version(request={"name": secret_name})
        zip_data = response.payload.data

        wallet_dir = os.path.join(os.getcwd(), "wallet")
        if not os.path.exists(wallet_dir):
            os.makedirs(wallet_dir)

        print(f"Extracting to {wallet_dir}...")
        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            z.extractall(wallet_dir)
        print("✅ Wallet extracted successfully.")
    except Exception as e:
        print(f"❌ Failed to download or extract wallet: {e}")

if __name__ == "__main__":
    prepare_wallet()
