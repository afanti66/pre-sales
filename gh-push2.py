#!/usr/bin/env python3
"""Push repo to GitHub via Contents API using gh CLI."""
import subprocess, json, os, base64, sys

def gh_api(method, path, data=None):
    cmd = ['gh', 'api', path, '--method', method]
    if data is not None:
        cmd += ['--input', '-']
        proc = subprocess.run(cmd, input=json.dumps(data), capture_output=True, text=True, timeout=60)
    else:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    output = proc.stdout
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {'error': output[:300], 'stderr': proc.stderr[:300]}

def main():
    repo = 'afanti66/pre-sales'
    base_dir = '/home/afanti/projects/sales-agent-dashboard'
    ignore_dirs = {'.git', '.hermes', '__pycache__', 'node_modules'}
    ignore_files = {'.DS_Store', 'gh-push.py'}
    
    # Collect files
    files = []
    for root, dirs, fnames in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
        for fname in fnames:
            if fname in ignore_files or fname.endswith('.pyc'):
                continue
            fpath = os.path.join(root, fname)
            relpath = os.path.relpath(fpath, base_dir)
            size = os.path.getsize(fpath)
            if size > 2 * 1024 * 1024:
                print(f"  SKIP (large): {relpath} ({size/1024:.0f}KB)")
                continue
            files.append((relpath, fpath, size))
    
    files.sort(key=lambda x: x[0])
    print(f"Total files: {len(files)}, total size: {sum(f[2] for f in files)/1024:.0f}KB")
    
    # Push each file via Contents API
    for i, (relpath, fpath, size) in enumerate(files):
        with open(fpath, 'rb') as f:
            content = f.read()
        
        # Always base64 - GitHub API is picky
        text = base64.b64encode(content).decode('ascii')
        encoding = 'base64'
        
        # Check if file already exists (for subsequent pushes, get SHA)
        # First push - no SHA needed
        
        data = {
            'message': f'Add {relpath}',
            'content': text,
            'encoding': encoding
        }
        
        result = gh_api('PUT', f'repos/{repo}/contents/{relpath}', data)
        
        if 'content' in result:
            if (i+1) % 10 == 0:
                print(f"  {i+1}/{len(files)} files pushed...")
        elif 'error' in result:
            print(f"  FAILED: {relpath} - {result['error']}")
            if 'stderr' in result:
                print(f"  STDERR: {result['stderr']}")
            return
        else:
            print(f"  FAILED: {relpath} - {json.dumps(result)[:200]}")
            return
    
    print(f"\n✅ All {len(files)} files pushed!")
    print(f"   https://github.com/{repo}")

if __name__ == '__main__':
    main()
