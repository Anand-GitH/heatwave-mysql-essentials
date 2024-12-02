import oci
from dataclasses import dataclass
from prettytable import PrettyTable
from typing import Optional, List

# Data classes for updated and skipped DB systems
@dataclass
class DBSystemInfoSkipped:
    """Represents a skipped DB system and the reason for skipping."""
    compartment_name: str
    db_system_id: str
    status: str
    reason_for_skipping: Optional[str] = None


@dataclass
class DBSystemInfoUpdated:
    """Represents an updated DB system with its operation status."""
    compartment_name: str
    db_system_id: str
    status: str
    operation_status: Optional[str] = None


def update_oci_tags(config: dict, namespace: str, tag_name: str):
    """
    Query MySQL DB systems and adds or skips tags based on conditions.

    Args:
        config (dict): OCI configuration.
        namespace (str): The namespace for defined tags.
        tag_name (str): The tag name to add or validate.
    """
    mysql_client = oci.mysql.DbSystemClient(config)
    identity_client = oci.identity.IdentityClient(config)

    db_systems_skipped: List[DBSystemInfoSkipped] = []
    db_systems_updated: List[DBSystemInfoUpdated] = []

    # Retrieve compartments
    compartments = identity_client.list_compartments(
        config['tenancy'], compartment_id_in_subtree=True
    ).data
    compartments.append(identity_client.get_compartment(config['tenancy']).data)

    for compartment in compartments:
        try:
            db_systems = mysql_client.list_db_systems(compartment_id=compartment.id).data

            for db_system in db_systems:
                if db_system.lifecycle_state != "ACTIVE":
                    
                    defined_tags = db_system.defined_tags.get(namespace, {})

                    if tag_name in defined_tags:
                        if defined_tags[tag_name] == db_system.id:
                            db_systems_skipped.append(DBSystemInfoSkipped(compartment_name=compartment.name,
                            db_system_id=db_system.display_name,
                            status=db_system.lifecycle_state,
                            reason_for_skipping="Tag already exists"
                            ))
                    else: 
                        db_systems_skipped.append(DBSystemInfoSkipped(
                        compartment_name=compartment.name,
                        db_system_id=db_system.display_name,
                        status=db_system.lifecycle_state,
                        reason_for_skipping="Tag update skipped as the DB system is not in an ACTIVE state."
                        ))
                    
                    continue

                defined_tags = db_system.defined_tags.get(namespace, {})
                if tag_name not in defined_tags or defined_tags[tag_name] != db_system.id:
                    defined_tags[tag_name] = db_system.id
                    update_db_system_details = oci.mysql.models.UpdateDbSystemDetails(
                        defined_tags={namespace: defined_tags}
                    )
                    response = mysql_client.update_db_system(
                        db_system_id=db_system.id,
                        update_db_system_details=update_db_system_details
                    )
                    if response:
                        db_systems_updated.append(DBSystemInfoUpdated(
                            compartment_name=compartment.name,
                            db_system_id=db_system.display_name,
                            status=db_system.lifecycle_state,
                            operation_status="Tag updated successfully"
                        ))
                    else:
                        db_systems_skipped.append(DBSystemInfoSkipped(
                            compartment_name=compartment.name,
                            db_system_id=db_system.display_name,
                            status=db_system.lifecycle_state,
                            reason_for_skipping="Failed to update tag"
                        ))
                else:
                    db_systems_skipped.append(DBSystemInfoSkipped(
                        compartment_name=compartment.name,
                        db_system_id=db_system.display_name,
                        status=db_system.lifecycle_state,
                        reason_for_skipping="Tag already exists"
                    ))

        except oci.exceptions.ServiceError as e:
            print(f"Error retrieving MySQL DB systems for compartment '{compartment.name}': {str(e)}")

    # Display results in tabular format
    display_results(db_systems_updated, db_systems_skipped)


def display_results(
    updated: List[DBSystemInfoUpdated], skipped: List[DBSystemInfoSkipped]
):
    """
    Displays the updated and skipped DB systems in a tabular format.

    Args:
        updated (List[DBSystemInfoUpdated]): List of updated DB systems.
        skipped (List[DBSystemInfoSkipped]): List of skipped DB systems.
    """
    table = PrettyTable()
    table.field_names = ["Compartment Name", "DB System ID", "DB Status", "Operation Status"]

    for db in updated:
        table.add_row([db.compartment_name, db.db_system_id, db.status, db.operation_status or "None"])

    for db in skipped:
        table.add_row([db.compartment_name, db.db_system_id, db.status, db.reason_for_skipping or "None"])

    print(table)


if __name__ == "__main__":
    config = oci.config.from_file()
    namespace = input("Enter your namespace: ")
    tag_name = input("Enter your tag name: ")

    update_oci_tags(config, namespace, tag_name)
