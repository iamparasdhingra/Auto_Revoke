import requests
import base64


def delete_github_file(repo_name, file_path, github_token):
    """
    Deletes a file from a GitHub repository using the API.
    Returns (success_boolean, message)
    """
    if not github_token:
        return False, "GITHUB_TOKEN is not configured in .env"

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }

    url = f"https://api.github.com/repos/{repo_name}/contents/{file_path}"
    
    # 1. Get the file's current SHA (required for deletion)
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return False, f"Could not find file on GitHub (Status {response.status_code})"
        
        file_sha = response.json().get("sha")
        if not file_sha:
            return False, "Could not retrieve file SHA."
    except Exception as e:
        return False, f"Error fetching file metadata: {e}"

    # 2. Delete the file
    delete_payload = {
        "message": f"🚨 Auto-Revoke Bot: Deleting file {file_path} due to leaked secret.",
        "sha": file_sha
    }
    
    try:
        del_response = requests.delete(url, headers=headers, json=delete_payload, timeout=5)
        if del_response.status_code in [200, 201]:
            return True, f"Successfully deleted {file_path} from {repo_name}!"
        else:
            return False, f"Failed to delete file (Status {del_response.status_code}): {del_response.text}"
    except Exception as e:
        return False, f"Error deleting file: {e}"


def redact_github_file(repo_name, file_path, secret_value, github_token):
    """
    Replaces the leaked secret value in the file with 'PUT_YOUR_API_KEY_HERE'.
    Returns (success, redaction_commit_sha, original_content, message)
    """
    if not github_token:
        return False, None, None, "GITHUB_TOKEN is not configured in .env"

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    url = f"https://api.github.com/repos/{repo_name}/contents/{file_path}"

    # 1. Fetch the file content and SHA
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return False, None, None, f"Could not find file (Status {response.status_code})"

        data = response.json()
        file_sha = data.get("sha")
        original_content = base64.b64decode(data.get("content", "")).decode("utf-8")
    except Exception as e:
        return False, None, None, f"Error fetching file: {e}"

    # 2. Replace the secret in the content
    redacted_content = original_content.replace(secret_value, "ENTER_YOUR_API_KEY_HERE")
    if redacted_content == original_content:
        return False, None, None, "Secret value not found in file content."

    # 3. Push the redacted version back to GitHub
    encoded_content = base64.b64encode(redacted_content.encode("utf-8")).decode("utf-8")
    update_payload = {
        "message": f"🔒 Auto-Revoke Bot: Redacted leaked secret in {file_path}",
        "content": encoded_content,
        "sha": file_sha
    }

    try:
        put_response = requests.put(url, headers=headers, json=update_payload, timeout=10)
        if put_response.status_code in [200, 201]:
            new_commit_sha = put_response.json()["commit"]["sha"]
            return True, new_commit_sha, original_content, f"Successfully redacted secret in {file_path}!"
        else:
            return False, None, None, f"Failed to update file (Status {put_response.status_code}): {put_response.text}"
    except Exception as e:
        return False, None, None, f"Error updating file: {e}"


def restore_github_file(repo_name, file_path, original_content, github_token):
    """
    Restores a file to its original content (undoes a redaction).
    Returns (success, message)
    """
    if not github_token:
        return False, "GITHUB_TOKEN is not configured in .env"

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    url = f"https://api.github.com/repos/{repo_name}/contents/{file_path}"

    # Get the current SHA to update it
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return False, f"Could not find file (Status {response.status_code})"
        file_sha = response.json().get("sha")
    except Exception as e:
        return False, f"Error fetching current file: {e}"

    encoded_content = base64.b64encode(original_content.encode("utf-8")).decode("utf-8")
    update_payload = {
        "message": "↩️ Auto-Revoke Bot: Restoring original file content (user requested undo)",
        "content": encoded_content,
        "sha": file_sha
    }

    try:
        put_response = requests.put(url, headers=headers, json=update_payload, timeout=10)
        if put_response.status_code in [200, 201]:
            return True, f"Successfully restored {file_path}!"
        else:
            return False, f"Failed to restore file (Status {put_response.status_code}): {put_response.text}"
    except Exception as e:
        return False, f"Error restoring file: {e}"
