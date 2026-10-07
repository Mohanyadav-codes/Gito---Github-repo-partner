import os
import re
import requests
from urllib.parse import urlparse

# Directories to exclude
EXCLUDED_DIRS = {
    '.git', 'node_modules', 'venv', '.venv', 'env', '__pycache__',
    'dist', 'build', 'target', 'vendor'
}

# File extensions to exclude (binary, media, datasets)
EXCLUDED_EXTENSIONS = {
    # Media / Images
    '.png', '.jpg', '.jpeg', '.gif', '.mp4', '.mkv', '.webm', '.ico', '.svg', '.webp',
    # Binaries / Archives
    '.zip', '.tar', '.gz', '.rar', '.exe', '.dll', '.so', '.dylib', '.pdf', '.bin',
    # Large datasets (unless explicitly needed)
    '.csv', '.sqlite', '.db', '.tsv'
}

# Specific files to exclude (lock files, secrets, configs)
EXCLUDED_FILES = {
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 
    '.env', 'credentials.json', 'client_secret.json',
    '.gitignore', '.dockerignore', '.eslintignore', '.prettierignore'
}

def is_excluded(path: str) -> bool:
    """
    Check if a file path should be excluded based on the defined rules.
    """
    parts = path.split('/')
    filename = parts[-1]
    
    # 1. Check if any parent directory is in the excluded list
    for part in parts[:-1]:
        if part in EXCLUDED_DIRS:
            return True
            
    # 2. Check exact file name matches
    if filename in EXCLUDED_FILES:
        return True
        
    # 3. Check for specific secrets/config names loosely
    if 'credential' in filename.lower() or 'secret' in filename.lower() or filename.startswith('.env'):
        return True
        
    # 4. Check for dotfile configs (like .oxlintrc.json, .eslintrc, etc.)
    if filename.startswith('.') and (filename.endswith('rc') or filename.endswith('rc.json') or filename.endswith('rc.yaml') or filename.endswith('rc.yml')):
        return True 
        
    # 4. Check file extensions
    _, ext = os.path.splitext(filename)
    if ext.lower() in EXCLUDED_EXTENSIONS:
        return True
        
    # 5. Check for minified files
    if filename.endswith('.min.js') or filename.endswith('.min.css'):
        return True
        
    # 6. Exclude JSON dumps if they are huge, but we can't easily know size here,
    # so we might exclude large JSONs or just let them through and filter by size later.
    # For now, we will download .json files unless they are lockfiles.

    return False

def parse_github_url(url: str):
    """Extract owner and repo from a github url."""
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split('/') if p]
    if len(path_parts) >= 2:
        return path_parts[0], path_parts[1]
    raise ValueError(f"Invalid GitHub URL: {url}")

def extract_repo(url: str, output_dir: str, token: str = None):
    """
    Extracts a repository via GitHub API and downloads non-excluded files.
    """
    owner, repo = parse_github_url(url)
    
    headers = {
        "Accept": "application/vnd.github.v3+json"
    }
    if token:
        headers["Authorization"] = f"token {token}"
        
    # 1. Get the default branch
    repo_url = f"https://api.github.com/repos/{owner}/{repo}"
    print(f"Fetching repository details for {owner}/{repo}...")
    
    resp = requests.get(repo_url, headers=headers)
    if resp.status_code != 200:
        print(f"Failed to fetch repo details: {resp.status_code} {resp.text}")
        return 0
        
    default_branch = resp.json().get('default_branch', 'main')
    
    # 2. Get the tree recursively
    tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
    print(f"Fetching file tree for branch '{default_branch}'...")
    
    resp = requests.get(tree_url, headers=headers)
    if resp.status_code != 200:
        print(f"Failed to fetch file tree: {resp.status_code} {resp.text}")
        return 0
        
    tree = resp.json().get('tree', [])
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    downloaded_count = 0
    skipped_count = 0
    
    print("Starting download...")
    for item in tree:
        if item['type'] == 'blob': # It's a file
            path = item['path']
            
            if is_excluded(path):
                # print(f"Skipped: {path}")
                skipped_count += 1
                continue
                
            # Download file
            # raw.githubusercontent.com doesn't count against standard API limits in the same way
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/{path}"
            
            try:
                # We can use the token for raw downloads too, useful for private repos
                file_resp = requests.get(raw_url, headers=headers)
                file_resp.raise_for_status()
                
                # Create directories if needed
                local_path = os.path.join(output_dir, path)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                with open(local_path, 'wb') as f:
                    f.write(file_resp.content)
                print(f"Downloaded: {path}")
                downloaded_count += 1
            except Exception as e:
                print(f"Failed to download {path}: {e}")
                
    print(f"\nExtraction complete!")
    print(f"Downloaded {downloaded_count} files to '{output_dir}'.")
    print(f"Skipped {skipped_count} excluded files.")
    return downloaded_count

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Extract a GitHub repository via API, filtering out unnecessary files.")
    parser.add_argument("url", help="GitHub repository URL")
    parser.add_argument("--output", "-o", default="repo_output", help="Output directory to save the repo")
    parser.add_argument("--token", "-t", default=os.getenv("GITHUB_TOKEN"), help="GitHub Personal Access Token (optional, but recommended to avoid rate limits)")
    
    args = parser.parse_args()
    extract_repo(args.url, args.output, args.token)
