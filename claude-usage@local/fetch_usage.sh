#!/bin/bash
# Fetch Claude Code usage information using tmux to interact with claude CLI

SESSION_NAME="claude_usage_fetch_$$"

# Kill any existing session with this name
tmux kill-session -t "$SESSION_NAME" 2>/dev/null

# Start a new detached tmux session running claude
tmux new-session -d -s "$SESSION_NAME" -x 120 -y 50 'claude --dangerously-skip-permissions'

# Wait for startup
sleep 2

# Press enter (for trust dialog if shown)
tmux send-keys -t "$SESSION_NAME" Enter
sleep 2

# Press enter again (in case of second prompt)
tmux send-keys -t "$SESSION_NAME" Enter
sleep 2

# Type /usage with spacing
for char in '/' 'u' 's' 'a' 'g' 'e'; do
    tmux send-keys -t "$SESSION_NAME" -l "$char"
    sleep 0.2
done

# Press Enter
tmux send-keys -t "$SESSION_NAME" Enter

# Wait for output to render
sleep 2

# Capture the pane content
OUTPUT=$(tmux capture-pane -t "$SESSION_NAME" -p)

# Kill the session
tmux send-keys -t "$SESSION_NAME" Escape
sleep 0.5
tmux send-keys -t "$SESSION_NAME" '/exit' Enter
sleep 1
tmux kill-session -t "$SESSION_NAME" 2>/dev/null

# Parse the output for usage percentages
echo "$OUTPUT" | python3 -c '
import sys
import re

text = sys.stdin.read()

# Find session usage
session_match = re.search(r"Current session.*?(\d+)%\s*used", text, re.DOTALL)
session_pct = session_match.group(1) if session_match else "??"

# Find weekly usage (all models)
weekly_match = re.search(r"Current week \(all models\).*?(\d+)%\s*used", text, re.DOTALL)
weekly_pct = weekly_match.group(1) if weekly_match else "??"

# Find weekly sonnet usage
sonnet_match = re.search(r"Current week \(Sonnet only\).*?(\d+)%\s*used", text, re.DOTALL)
sonnet_pct = sonnet_match.group(1) if sonnet_match else "??"

# Find extra usage
extra_match = re.search(r"Extra usage.*?(\d+)%\s*used", text, re.DOTALL)
extra_pct = extra_match.group(1) if extra_match else None

# Calculate remaining
session_remaining = 100 - int(session_pct) if session_pct != "??" else "??"
weekly_remaining = 100 - int(weekly_pct) if weekly_pct != "??" else "??"

# Output in parseable format
print(f"SESSION_USED={session_pct}")
print(f"SESSION_REMAINING={session_remaining}")
print(f"WEEKLY_USED={weekly_pct}")
print(f"WEEKLY_REMAINING={weekly_remaining}")
print(f"SONNET_USED={sonnet_pct}")
if extra_pct:
    print(f"EXTRA_USED={extra_pct}")

# Human readable
print(f"Session: {session_remaining}% remaining")
print(f"Weekly: {weekly_remaining}% remaining")
'
