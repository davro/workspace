#!/bin/bash

usage() {
    echo "Usage: $0 <start|stop>"
    exit 1
}

start() {
    echo "Starting the application"
    # Add your start logic here

    echo "Music (groovesalad) !"
    vlc ~/workspace/data/music/groovesalad130.pls &

    echo "Telegram !"
    ~/workspace/apps/telegram/Telegram &

    # Stay away from the chumps.
    echo "Discord !"
    ~/workspace/apps/discord-core/Discord/Discord &

    echo "LibreOffice Data"
    libreoffice /media/davro/6662-3462/personal/data.ods &
}

stop() {
    echo "Stopping the application"
    # Add your stop logic here

    echo "Music (groovesalad) !"
    #vlc ~/workspace/data/music/groovesalad130.pls &
    pkill -f vlc

    echo "Telegram !"
    #~/workspace/telegram/Telegram &
    pkill -f Telegram

    # Stay away from the chumps.
    echo "Discord !"
    #~/workspace/discord/Discord &
    pkill -f Discord
}

if [ $# -ne 1 ]; then
    usage
fi

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    *)
        usage
        ;;
esac


