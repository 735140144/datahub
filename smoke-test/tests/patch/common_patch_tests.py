import time
import uuid
from typing import Dict, Optional, Type

from datahub.emitter.mce_builder import (make_tag_urn, make_term_urn,
                                         make_user_urn)
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.mcp_patch_builder import MetadataPatchProposal
from datahub.ingestion.graph.client import DataHubGraph, DataHubGraphConfig
from datahub.metadata.schema_classes import (AuditStampClass, GlobalTagsClass,
                                             GlossaryTermAssociationClass,
                                             GlossaryTermsClass, OwnerClass,
                                             OwnershipClass,
                                             OwnershipTypeClass,
                                             TagAssociationClass, _Aspect)


def helper_test_entity_terms_patch(
    test_entity_urn: str, patch_builder_class: Type[MetadataPatchProposal]
):
    def get_terms(graph, entity_urn):
        return graph.get_aspect(
            entity_urn=entity_urn,
            aspect_type=GlossaryTermsClass,
        )

    term_urn = make_term_urn(term=f"testTerm-{uuid.uuid4()}")

    term_association = GlossaryTermAssociationClass(urn=term_urn, context="test")
    global_terms = GlossaryTermsClass(
        terms=[term_association],
        auditStamp=AuditStampClass(
            time=int(time.time() * 1000.0), actor=make_user_urn("tester")
        ),
    )
    mcpw = MetadataChangeProposalWrapper(entityUrn=test_entity_urn, aspect=global_terms)

    with DataHubGraph(DataHubGraphConfig()) as graph:
        graph.emit_mcp(mcpw)
        terms_read = get_terms(graph, test_entity_urn)
        assert terms_read.terms[0].urn == term_urn
        assert terms_read.terms[0].context == "test"

        new_term = GlossaryTermAssociationClass(
            urn=make_term_urn(f"test-{uuid.uuid4()}")
        )
        patch_builder = patch_builder_class(test_entity_urn)
        assert hasattr(patch_builder, "add_term")
        for patch_mcp in patch_builder.add_term(new_term).build():
            graph.emit_mcp(patch_mcp)
            pass

        terms_read = get_terms(graph, test_entity_urn)

        assert terms_read.terms[0].urn == term_urn
        assert terms_read.terms[0].context == "test"
        assert terms_read.terms[1].urn == new_term.urn
        assert terms_read.terms[1].context is None

        for patch_mcp in (
            patch_builder_class(test_entity_urn).remove_term(term_urn).build()
        ):
            graph.emit_mcp(patch_mcp)
            pass

        terms_read = get_terms(graph, test_entity_urn)
        assert len(terms_read.terms) == 1
        assert terms_read.terms[0].urn == new_term.urn


def helper_test_dataset_tags_patch(
    test_entity_urn: str, patch_builder_class: Type[MetadataPatchProposal]
):

    tag_urn = make_tag_urn(tag=f"testTag-{uuid.uuid4()}")

    tag_association = TagAssociationClass(tag=tag_urn, context="test")
    global_tags = GlobalTagsClass(tags=[tag_association])
    mcpw = MetadataChangeProposalWrapper(entityUrn=test_entity_urn, aspect=global_tags)

    with DataHubGraph(DataHubGraphConfig()) as graph:
        graph.emit_mcp(mcpw)
        tags_read: GlobalTagsClass = graph.get_aspect(
            entity_urn=test_entity_urn,
            aspect_type=GlobalTagsClass,
        )
        assert tags_read.tags[0].tag == tag_urn
        assert tags_read.tags[0].context == "test"

        new_tag = TagAssociationClass(tag=make_tag_urn(f"test-{uuid.uuid4()}"))
        patch_builder = patch_builder_class(test_entity_urn)
        assert hasattr(patch_builder, "add_tag")
        for patch_mcp in patch_builder.add_tag(new_tag).build():
            graph.emit_mcp(patch_mcp)
            pass

        tags_read = graph.get_aspect(
            entity_urn=test_entity_urn,
            aspect_type=GlobalTagsClass,
        )
        assert tags_read.tags[0].tag == tag_urn
        assert tags_read.tags[0].context == "test"
        assert tags_read.tags[1].tag == new_tag.tag
        assert tags_read.tags[1].context is None

        for patch_mcp in (
            patch_builder_class(test_entity_urn).remove_tag(tag_urn).build()
        ):
            graph.emit_mcp(patch_mcp)
            pass

        tags_read = graph.get_aspect(
            entity_urn=test_entity_urn,
            aspect_type=GlobalTagsClass,
        )
        assert len(tags_read.tags) == 1
        assert tags_read.tags[0].tag == new_tag.tag


def helper_test_ownership_patch(
    test_entity_urn: str, patch_builder_class: Type[MetadataPatchProposal]
):
    owner_to_set = OwnerClass(
        owner=make_user_urn("jdoe"), type=OwnershipTypeClass.DATAOWNER
    )
    ownership_to_set = OwnershipClass(owners=[owner_to_set])

    owner_to_add = OwnerClass(
        owner=make_user_urn("gdoe"), type=OwnershipTypeClass.DATAOWNER
    )
    mcpw = MetadataChangeProposalWrapper(
        entityUrn=test_entity_urn, aspect=ownership_to_set
    )
    with DataHubGraph(DataHubGraphConfig()) as graph:
        graph.emit_mcp(mcpw)
        owner: OwnershipClass = graph.get_aspect(
            entity_urn=test_entity_urn, aspect_type=OwnershipClass
        )
        assert owner.owners[0].owner == make_user_urn("jdoe")

        for patch_mcp in (
            patch_builder_class(test_entity_urn).add_owner(owner_to_add).build()
        ):
            graph.emit_mcp(patch_mcp)

        owner = graph.get_aspect(entity_urn=test_entity_urn, aspect_type=OwnershipClass)
        assert len(owner.owners) == 2

        for patch_mcp in (
            patch_builder_class(test_entity_urn)
            .remove_owner(make_user_urn("gdoe"))
            .build()
        ):
            graph.emit_mcp(patch_mcp)

        owner = graph.get_aspect(entity_urn=test_entity_urn, aspect_type=OwnershipClass)
        assert len(owner.owners) == 1
        assert owner.owners[0].owner == make_user_urn("jdoe")


def helper_test_custom_properties_patch(
    test_entity_urn: str,
    patch_builder_class: Type[MetadataPatchProposal],
    custom_properties_aspect_class: Type[_Aspect],
    base_aspect: _Aspect,
):
    def get_custom_properties(
        graph: DataHubGraph, entity_urn: str
    ) -> Optional[Dict[str, str]]:
        custom_properties_aspect = graph.get_aspect(
            entity_urn=entity_urn,
            aspect_type=custom_properties_aspect_class,
        )
        assert custom_properties_aspect
        return custom_properties_aspect.customProperties

    base_property_map = {"base_property": "base_property_value"}

    orig_aspect = base_aspect
    assert hasattr(orig_aspect, "customProperties")
    orig_aspect.customProperties = base_property_map
    mcpw = MetadataChangeProposalWrapper(entityUrn=test_entity_urn, aspect=orig_aspect)

    with DataHubGraph(DataHubGraphConfig()) as graph:
        graph.emit(mcpw)
        # assert custom properties looks as expected
        custom_properties = get_custom_properties(graph, test_entity_urn)
        assert custom_properties
        for k, v in base_property_map.items():
            assert custom_properties[k] == v

        new_properties = {
            "test_property": "test_value",
            "test_property1": "test_value1",
        }

        entity_patch_builder = patch_builder_class(test_entity_urn)
        for k, v in new_properties.items():
            entity_patch_builder.add_custom_property(k, v)

        for patch_mcp in entity_patch_builder.build():
            graph.emit_mcp(patch_mcp)

        custom_properties = get_custom_properties(graph, test_entity_urn)

        assert custom_properties is not None
        for k, v in new_properties.items():
            assert custom_properties[k] == v

        # ensure exising properties were not touched
        for k, v in base_property_map.items():
            assert custom_properties[k] == v

        # Remove property
        for patch_mcp in (
            patch_builder_class(test_entity_urn)
            .remove_custom_property("test_property")
            .build()
        ):
            graph.emit_mcp(patch_mcp)

        custom_properties = get_custom_properties(graph, test_entity_urn)

        assert custom_properties is not None
        assert "test_property" not in custom_properties
        assert custom_properties["test_property1"] == "test_value1"

        # ensure exising properties were not touched
        for k, v in base_property_map.items():
            assert custom_properties[k] == v

        # Replace custom properties
        for patch_mcp in (
            patch_builder_class(test_entity_urn)
            .set_custom_properties(new_properties)
            .build()
        ):
            graph.emit_mcp(patch_mcp)

        custom_properties = get_custom_properties(graph, test_entity_urn)

        assert custom_properties is not None
        for k in base_property_map:
            assert k not in custom_properties
        for k, v in new_properties.items():
            assert custom_properties[k] == v

        # ensure existing fields were not touched
        full_aspect: Optional[_Aspect] = graph.get_aspect(
            test_entity_urn, custom_properties_aspect_class
        )

        assert full_aspect
        for k, v in orig_aspect.__dict__.items():
            assert full_aspect.__dict__[k] == v
