import boto3
from botocore.exceptions import ClientError


def revoke_aws_key(leaked_access_key_id, admin_access_key, admin_secret_key):
    """
    Uses YOUR admin AWS credentials to deactivate someone else's
    (the leaked) access key.
    """
    try:
        iam = boto3.client(
            "iam",
            aws_access_key_id=admin_access_key,
            aws_secret_access_key=admin_secret_key,
        )

        # Note: update_access_key needs the username the key belongs to.
        # In a real scenario you'd look this up via iam.get_access_key_last_used()
        # or track it when you create the demo key. For the hackathon demo,
        # hardcode the known demo username.
        iam.update_access_key(
            AccessKeyId=leaked_access_key_id,
            Status="Inactive",
            UserName="demo-leak-user",  # <-- change to your test IAM user
        )
        return True
    except ClientError as e:
        print(f"Failed to revoke key: {e}")
        return False
