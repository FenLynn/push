import os
import boto3

# Load env manually
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip() and not line.strip().startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    if k.strip() not in os.environ:
                        os.environ[k.strip()] = v.strip()

load_env()
s3 = boto3.client(
    's3',
    endpoint_url=os.getenv('R2_ENDPOINT'),
    aws_access_key_id=os.getenv('R2_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('R2_SECRET_KEY')
)

print("Listing bucket:", os.getenv('R2_BUCKET_NAME'))
try:
    resp = s3.list_objects_v2(Bucket=os.getenv('R2_BUCKET_NAME'))
    if 'Contents' in resp:
        for obj in resp['Contents']:
            print(f"- {obj['Key']} ({obj['Size']})")
    else:
        print("Bucket is empty according to API.")
except Exception as e:
    print("Error:", e)
