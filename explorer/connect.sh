#!/bin/bash
# Open the AI Village explorer from your Mac: start the instance if stopped, wait for the dashboard,
# then forward localhost:8501 through SSM (no inbound ports on the instance).
# Needs: AWS CLI + session-manager-plugin (brew install --cask session-manager-plugin).
set -euo pipefail
INSTANCE="i-0ed2e0636c29e833d"
REGION="ap-south-1"
PORT="${PORT:-8501}"

state=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE" \
  --query 'Reservations[0].Instances[0].State.Name' --output text)
if [ "$state" = "stopped" ]; then
  echo "Starting $INSTANCE (billed at \$0.273/hr while running; stops itself after 60 min idle)…"
  aws ec2 start-instances --region "$REGION" --instance-ids "$INSTANCE" >/dev/null
fi
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE"
echo "Waiting for the SSM agent…"
until [ "$(aws ssm describe-instance-information --region "$REGION" \
  --filters "Key=InstanceIds,Values=$INSTANCE" --query 'InstanceInformationList[0].PingStatus' --output text)" = "Online" ]; do
  sleep 5
done
echo "Open http://localhost:$PORT  (Ctrl+C to close the tunnel)"
aws ssm start-session --region "$REGION" --target "$INSTANCE" \
  --document-name AWS-StartPortForwardingSession \
  --parameters "portNumber=8501,localPortNumber=$PORT"
