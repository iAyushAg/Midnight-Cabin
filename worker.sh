#!/bin/bash

while true
do
  echo "Running pipeline..."
  bash run_pipeline.sh
  echo "Sleeping 12 hours..."
  sleep 43200
done