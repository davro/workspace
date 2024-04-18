#!/bin/bash

function clone_or_update_repo() {
    local repo_url=$1
    local repo_dir=$2

    # Check if the directory exists
    if [ -d "$repo_dir" ]; then
        echo "Workspace Repository Updating ..."
        # Change directory to the repository
        cd "$repo_dir" || return
        # Pull latest changes from the repository
        git pull
    else
        echo "Workspace Repository Cloning ..."
        # Clone the repository
        git clone "$repo_url" "$repo_dir"
    fi
}

# workspace repo's
clone_or_update_repo "git@github.com:davro/cpp.git" "cpp"
clone_or_update_repo "git@github.com:davro/go.git" "go"
clone_or_update_repo "git@github.com:davro/python.git" "python"

