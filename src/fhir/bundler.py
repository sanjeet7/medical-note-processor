"""
FHIR Bundle Assembler

Creates a FHIR Bundle (collection type) containing all resources
generated from the structured medical data extraction.
"""
from typing import List, Dict, Any
from datetime import datetime, timezone
import uuid

from fhir.resources.bundle import Bundle, BundleEntry
from fhir.resources.resource import Resource


def generate_bundle_id() -> str:
    """Generate a unique bundle ID."""
    return str(uuid.uuid4())


class FHIRBundler:
    """
    Assembles FHIR resources into a Bundle.
    
    Creates a collection-type Bundle containing all resources
    from a structured medical note extraction.
    """
    
    def __init__(self):
        """Initialize the bundler."""
        self.entries: List[BundleEntry] = []
    
    def add_resource(self, resource: Resource) -> None:
        """
        Add a resource to the bundle.
        
        Args:
            resource: FHIR resource to add
        """
        entry = BundleEntry(
            fullUrl=f"urn:uuid:{resource.id}",
            resource=resource
        )
        self.entries.append(entry)
    
    def add_resources(self, resources: List[Resource]) -> None:
        """
        Add multiple resources to the bundle.
        
        Args:
            resources: List of FHIR resources to add
        """
        for resource in resources:
            self.add_resource(resource)
    
    def build(self, bundle_id: str = None) -> Bundle:
        """
        Build the final FHIR Bundle.
        
        Args:
            bundle_id: Optional bundle ID (generated if not provided)
            
        Returns:
            FHIR Bundle containing all added resources
        """
        bundle_id = bundle_id or generate_bundle_id()
        
        bundle = Bundle(
            id=bundle_id,
            type="collection",
            timestamp=datetime.now(timezone.utc).isoformat(),
            entry=self.entries if self.entries else None
        )
        
        return bundle
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Build and return the bundle as a dictionary.
        
        Returns:
            Bundle as a dictionary (JSON-serializable)
        """
        bundle = self.build()
        return bundle.dict(exclude_none=True)
    
    def to_json(self, indent: int = 2) -> str:
        """
        Build and return the bundle as a JSON string.
        
        Args:
            indent: JSON indentation level
            
        Returns:
            Bundle as a JSON string
        """
        bundle = self.build()
        return bundle.json(indent=indent, exclude_none=True)
    
    @property
    def resource_count(self) -> int:
        """Number of resources in the bundle."""
        return len(self.entries)
    
    def get_resource_types(self) -> List[str]:
        """Get list of resource types in the bundle."""
        return [entry.resource.resource_type for entry in self.entries]
    
    def clear(self) -> None:
        """Clear all entries from the bundle."""
        self.entries = []
