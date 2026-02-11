#!/bin/bash
# Manual Push All Generated Content (with 5s delay)
export PYTHONPATH=$(pwd)

echo "Pushing morning..."
python main.py send morning
sleep 5

echo "Pushing finance..."
python main.py send finance
sleep 5

echo "Pushing stock..."
python main.py send stock
sleep 5

echo "Pushing fund..."
python main.py send fund
sleep 5

echo "Pushing etf..."
python main.py send etf
sleep 5

echo "Pushing night..."
python main.py send night
sleep 5

echo "Pushing life..."
python main.py send life
sleep 5

echo "Pushing game..."
python main.py send game
sleep 5

echo "Pushing estate..."
python main.py send estate
sleep 5

echo "Pushing damai..."
python main.py send damai
sleep 5

echo "Pushing paper (multi-page)..."
if [ -f "output/paper/latest.html" ]; then
    python main.py send --file output/paper/latest.html --title "Paper (Page 1)"
    sleep 5
fi
if [ -f "output/paper/latest_1.html" ]; then
    python main.py send --file output/paper/latest_1.html --title "Paper (Page 2)"
    sleep 5
fi
if [ -f "output/paper/latest_2.html" ]; then
    python main.py send --file output/paper/latest_2.html --title "Paper (Page 3)"
    sleep 5
fi
if [ -f "output/paper/latest_3.html" ]; then
    python main.py send --file output/paper/latest_3.html --title "Paper (Page 4)"
    sleep 5
fi

echo "Done."
