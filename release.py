import os
import json
from subprocess import check_call
from configparser import ConfigParser
import git
import requests
from datetime import datetime


def read_file(path, fname, content_type=None):
    p = os.path.join(path, fname)
    with open(p) as f:
        if content_type in ('json',):
            data = json.load(f)
        else:
            data = f.read()
    return data


def read_version(path):
    config = ConfigParser()
    config.read(os.path.join(path, 'setup.cfg'))
    return config.get('metadata', 'version')


def now():
    return '%s+00:00' % datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


DIR_PATH = os.path.dirname(os.path.realpath(__file__))
GIT_API_URL = 'https://api.github.com/repos/labsyspharm/OMERO_scripts'
VERSION = read_version(DIR_PATH)

# Get configuration
repo = git.Repo(DIR_PATH)
assert not repo.bare
username = repo.config_reader().get_value('user', 'name')
email = repo.config_reader().get_value('user', 'email')
token = read_file(os.path.expanduser('~/'), '.git_release_token').strip()
head = repo.commit('HEAD').hexsha
auth = requests.auth.HTTPBasicAuth(username, token)

# Ensure that there are no changes in this repository, staged or otherwise
if repo.is_dirty():
    print('Repository has changes, commit changes before releasing for safety')
    exit(1)

# Ensure the commit exists on gitHub
existing_commit_url = '%s/commits/%s' % (GIT_API_URL, head)
existing_commit = requests.get(existing_commit_url, auth=auth)
if not existing_commit.ok:
    print('Commit is not on GitHub, push before releasing')
    exit(1)

# Ensure this tag does not already exist
existing_tag_url = '%s/git/refs/tags/v%s' % (GIT_API_URL, VERSION)
existing_tag = requests.get(existing_tag_url, auth=auth)
if existing_tag.status_code != 404:
    print('Tag already exists on GitHub, version number might need bumping')
    exit(1)

# Create the tag on GitHub
create_tag_url = '%s/git/tags' % GIT_API_URL
create_tag_payload = {
    'tag': 'v%s' % VERSION,
    'message': 'Version %s' % VERSION,
    'object': head,
    'type': 'commit',
    'tagger': {
        'name': username,
        'email': email,
        'date': now()
    }
}
print('Creating tag...')
create_tag = requests.post(create_tag_url, json=create_tag_payload, auth=auth)
if not create_tag.ok:
    print('Tag creation failed')
    exit(1)

# Create the tag reference on GitHub
create_ref_url = '%s/git/refs' % GIT_API_URL
create_ref_payload = {
    'ref': 'refs/tags/v%s' % (VERSION),
    'sha': create_tag.json()['sha']
}
print('Creating tag reference...')
create_ref = requests.post(create_ref_url, json=create_ref_payload, auth=auth)
if not create_ref.ok:
    print('Tag reference creation failed')
    exit(1)

# Create the release on gitHub
create_release_url = '%s/releases' % GIT_API_URL
create_release_payload = {
    'tag_name': 'v%s' % VERSION,
    'name': 'OMERO_scripts %s' % VERSION
}
print('Creating release...')
create_release = requests.post(create_release_url,
                               json=create_release_payload, auth=auth)
if not create_release.ok:
    print('Release creation failed')
    exit(1)

print('Fetching newly created references...')
for remote in repo.remotes:
    remote.fetch()

print('Successful release of OMERO_scripts %s' % VERSION)
