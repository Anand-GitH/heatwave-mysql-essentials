#!/bin/bash

# Parameters: Namespace, Tag Name
NAMESPACE=$1
TAG_NAME=$2

# Check if parameters are provided
if [ -z "$NAMESPACE" ] || [ -z "$TAG_NAME" ]; then
    echo "Usage: $0 <namespace> <tag-name>"
    exit 1
fi

# Retrieve all compartments
COMPARTMENTS=$(oci iam compartment list --all --include-root --compartment-id-in-subtree true --query 'data[*].[id, name]' --output json)

printf "%-30s %-30s %-30s %-100s\n" "Compartment Name" "DB Name" "DB Status" "Reason"
printf "%-30s %-30s %-30s %-100s\n" "------------------------------" "------------------------------" "------------------------------" "----------------------------------------------------------------------------"

# Loop through each compartment
for COMPARTMENT in $(echo "$COMPARTMENTS" | jq -r '.[] | @base64'); do
    # Decode the base64 encoded compartment object
    COMPARTMENT_OBJ=$(echo "$COMPARTMENT" | base64 --decode)
  
  # Extract compartment ID and name
    COMPARTMENT_ID=$(echo "$COMPARTMENT_OBJ" | jq -r '.[0]')
    COMPARTMENT_NAME=$(echo "$COMPARTMENT_OBJ" | jq -r '.[1]')


  # List MySQL DB systems in the compartment
  DB_SYSTEMS=$(oci mysql db-system list --all --compartment-id "$COMPARTMENT_ID" --output json)

  # Loop through each DB system
  echo "$DB_SYSTEMS" | jq -c '.data[]' | while read -r obj; do

    DB_NAME=$(echo "$obj" | jq -r '.["display-name"]')
    DB_LIFECYCLE_STATE=$(echo "$obj" | jq -r '.["lifecycle-state"]')
    DB_ID=$(echo "$obj" | jq -r '.["id"]')


    if [ "$DB_LIFECYCLE_STATE" != "ACTIVE" ]; then
      # Retrieve existing defined tags
      DEFINED_TAGS=$(echo "$obj" | jq -r --arg NS "$NAMESPACE" '.["defined-tags"][$NS] // {}')
      EXISTING_TAG=$(echo "$DEFINED_TAGS" | jq -r --arg TAG "$TAG_NAME" '.[$TAG] // empty')


      # Check if the tag already exists and matches
      if [ "$EXISTING_TAG" == "$DB_ID" ]; then
        REASON="Tag already exists"
        printf "%-30s %-30s %-30s %-100s\n" "$COMPARTMENT_NAME" "$DB_NAME" "$DB_LIFECYCLE_STATE" "$REASON"
      else
        REASON="Tag update skipped as the DB system is not in ACTIVE state."
        printf "%-30s %-30s %-30s %-100s\n" "$COMPARTMENT_NAME" "$DB_NAME" "$DB_LIFECYCLE_STATE" "$REASON"
      fi
      continue
    fi
    
    # Retrieve existing defined tags
    DEFINED_TAGS=$(echo "$obj" | jq -r --arg NS "$NAMESPACE" '.["defined-tags"][$NS] // {}')
    EXISTING_TAG=$(echo "$DEFINED_TAGS" | jq -r --arg TAG "$TAG_NAME" '.[$TAG] // empty')

    # Check if the tag already exists and matches
    if [ "$EXISTING_TAG" == "$DB_ID" ]; then
      REASON="Tag already exists"
      printf "%-30s %-30s %-30s %-100s\n" "$COMPARTMENT_NAME" "$DB_NAME" "$DB_LIFECYCLE_STATE" "$REASON"
    else
      # Construct defined tags JSON
      UPDATED_DEFINED_TAGS=$(jq -n --arg namespace "$NAMESPACE" --arg tag_name "$TAG_NAME" --arg tag_value "$DB_ID" \
        '{($namespace): {($tag_name): $tag_value}}')

      # Update the DB system with new defined tags
      oci mysql db-system update \
        --db-system-id "$DB_ID" \
        --defined-tags "$UPDATED_DEFINED_TAGS" \
        --force

      REASON="Tag updated successfully"
      printf "%-30s %-30s %-30s %-100s\n" "$COMPARTMENT_NAME" "$DB_NAME" "$DB_LIFECYCLE_STATE" "$REASON"
    fi
  done
done


