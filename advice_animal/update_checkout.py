import posixpath
import subprocess
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse


def get_local_cache_name(url: str) -> str:
    # this isn't intended to be "secure" and we could just as easily use crc32
    # but starting with a secure hash keeps linters quiet.
    url_hash = sha256(url.encode()).hexdigest()

    path = urlparse(url).path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    repo_name = posixpath.basename(path)
    return f"{repo_name}-{url_hash[:8]}"


def update_local_cache(url: str, skip_update: bool) -> Path:
    import appdirs

    cache_dir = Path(appdirs.user_cache_dir("advice-animal", "advice-animal"))
    local_checkout = cache_dir / get_local_cache_name(url)
    if not local_checkout.exists():
        subprocess.check_output(["git", "clone", url, local_checkout])
    elif not skip_update:
        subprocess.check_output(["git", "pull"], cwd=local_checkout)
    return local_checkout
