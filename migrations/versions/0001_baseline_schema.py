"""baseline_schema - capture all pre-Alembic core domain tables

Revision ID: 0001_baseline_schema
Revises:
Create Date: 2026-09-07

This migration materialises the 13 core domain tables that were created by
SQLAlchemy ``create_all()`` before Alembic was introduced.

Upgrade logic:
  - Uses ``op.get_bind()`` + ``inspect`` to detect already-existing tables,
    so that existing databases (which already have these tables) skip the
    CREATE TABLE statements without error.  Fresh databases get the full DDL.

Downgrade:
  - Drops all 13 tables (fresh-DB teardown only — not for production rollback).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '0001_baseline_schema'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(inspector: sa.engine.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # 1. user_profiles
    if not _table_exists(inspector, 'user_profiles'):
        op.create_table(
            'user_profiles',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('target_goal', sa.Text(), nullable=False),
            sa.Column('target_role', sa.String(length=200), nullable=False, server_default=''),
            sa.Column('current_level', sa.String(length=20), nullable=False, server_default='missing'),
            sa.Column('current_skills_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('programming_languages_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('previous_experience', sa.Text(), nullable=False, server_default=''),
            sa.Column('completed_projects_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('preferred_technologies_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('preferred_industry', sa.String(length=200), nullable=False, server_default=''),
            sa.Column('target_markets_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('learning_preferences_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('budget', sa.String(length=20), nullable=False, server_default='any'),
            sa.Column('constraints_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('study_hours_per_day', sa.Float(), nullable=False, server_default='2.0'),
            sa.Column('deadline_months', sa.Integer(), nullable=False, server_default='12'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_user_profiles')),
        )

    # 2. skills
    if not _table_exists(inspector, 'skills'):
        op.create_table(
            'skills',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('profile_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('category', sa.String(length=100), nullable=False, server_default='general'),
            sa.Column('description', sa.Text(), nullable=False, server_default=''),
            sa.Column('current_level', sa.String(length=20), nullable=False, server_default='missing'),
            sa.Column('target_level', sa.String(length=20), nullable=False, server_default='proficient'),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
            sa.Column('priority', sa.String(length=20), nullable=False, server_default='medium'),
            sa.Column('market_demand_score', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('goal_relevance_score', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('estimated_hours', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('prerequisite_names_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('evidence_ids_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['profile_id'], ['user_profiles.id'],
                name=op.f('fk_skills_profile_id_user_profiles'),
                ondelete='CASCADE',
            ),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_skills')),
        )

    # 3. skill_dependencies
    if not _table_exists(inspector, 'skill_dependencies'):
        op.create_table(
            'skill_dependencies',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('from_skill_id', sa.String(length=36), nullable=False),
            sa.Column('to_skill_id', sa.String(length=36), nullable=False),
            sa.Column('dependency_type', sa.String(length=20), nullable=False, server_default='requires'),
            sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('source', sa.String(length=50), nullable=False, server_default='manual'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['from_skill_id'], ['skills.id'],
                name=op.f('fk_skill_dependencies_from_skill_id_skills'),
                ondelete='CASCADE',
            ),
            sa.ForeignKeyConstraint(
                ['to_skill_id'], ['skills.id'],
                name=op.f('fk_skill_dependencies_to_skill_id_skills'),
                ondelete='CASCADE',
            ),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_skill_dependencies')),
        )

    # 4. roadmaps
    if not _table_exists(inspector, 'roadmaps'):
        op.create_table(
            'roadmaps',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('profile_id', sa.String(length=36), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('objective', sa.Text(), nullable=False, server_default=''),
            sa.Column('total_estimated_hours', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('total_weeks', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('assumptions_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('skipped_skill_names_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('research_run_id', sa.String(length=36), nullable=False, server_default=''),
            sa.Column('quality_score', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('generated_at', sa.DateTime(), nullable=False),
            sa.Column('last_updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['profile_id'], ['user_profiles.id'],
                name=op.f('fk_roadmaps_profile_id_user_profiles'),
                ondelete='CASCADE',
            ),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_roadmaps')),
        )

    # 5. roadmap_phases
    if not _table_exists(inspector, 'roadmap_phases'):
        op.create_table(
            'roadmap_phases',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('roadmap_id', sa.String(length=36), nullable=False),
            sa.Column('phase_number', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('objective', sa.Text(), nullable=False, server_default=''),
            sa.Column('estimated_weeks', sa.Float(), nullable=False, server_default='4.0'),
            sa.Column('is_completed', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('skill_ids_json', sa.Text(), nullable=False, server_default='[]'),
            sa.ForeignKeyConstraint(
                ['roadmap_id'], ['roadmaps.id'],
                name=op.f('fk_roadmap_phases_roadmap_id_roadmaps'),
                ondelete='CASCADE',
            ),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_roadmap_phases')),
        )

    # 6. milestones
    if not _table_exists(inspector, 'milestones'):
        op.create_table(
            'milestones',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('phase_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=False, server_default=''),
            sa.Column('exit_criteria_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('estimated_weeks', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('is_achieved', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('achieved_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ['phase_id'], ['roadmap_phases.id'],
                name=op.f('fk_milestones_phase_id_roadmap_phases'),
                ondelete='CASCADE',
            ),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_milestones')),
        )

    # 7. learning_resources
    if not _table_exists(inspector, 'learning_resources'):
        op.create_table(
            'learning_resources',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('phase_id', sa.String(length=36), nullable=False),
            sa.Column('title', sa.String(length=300), nullable=False),
            sa.Column('resource_type', sa.String(length=20), nullable=False, server_default='course'),
            sa.Column('url', sa.Text(), nullable=False, server_default=''),
            sa.Column('provider', sa.String(length=200), nullable=False, server_default=''),
            sa.Column('difficulty', sa.String(length=20), nullable=False, server_default='familiar'),
            sa.Column('estimated_hours', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('cost', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('is_free', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('freshness_year', sa.Integer(), nullable=False, server_default='2024'),
            sa.Column('quality_score', sa.Float(), nullable=False, server_default='0.5'),
            sa.Column('associated_skill_names_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('source_id', sa.String(length=36), nullable=False, server_default=''),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['phase_id'], ['roadmap_phases.id'],
                name=op.f('fk_learning_resources_phase_id_roadmap_phases'),
                ondelete='CASCADE',
            ),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_learning_resources')),
        )

    # 8. projects
    if not _table_exists(inspector, 'projects'):
        op.create_table(
            'projects',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('phase_id', sa.String(length=36), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=False, server_default=''),
            sa.Column('required_skill_names_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('difficulty', sa.String(length=20), nullable=False, server_default='familiar'),
            sa.Column('expected_outcome', sa.Text(), nullable=False, server_default=''),
            sa.Column('portfolio_value', sa.Float(), nullable=False, server_default='0.5'),
            sa.Column('estimated_hours', sa.Float(), nullable=False, server_default='20.0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['phase_id'], ['roadmap_phases.id'],
                name=op.f('fk_projects_phase_id_roadmap_phases'),
                ondelete='CASCADE',
            ),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_projects')),
        )

    # 9. sources
    if not _table_exists(inspector, 'sources'):
        op.create_table(
            'sources',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('url', sa.String(length=2048), nullable=False),
            sa.Column('title', sa.String(length=500), nullable=False, server_default=''),
            sa.Column('source_type', sa.String(length=20), nullable=False, server_default='other'),
            sa.Column('publisher', sa.String(length=200), nullable=False, server_default=''),
            sa.Column('domain', sa.String(length=200), nullable=False, server_default=''),
            sa.Column('retrieved_at', sa.DateTime(), nullable=False),
            sa.Column('published_at', sa.DateTime(), nullable=True),
            sa.Column('reliability_score', sa.Float(), nullable=False, server_default='0.5'),
            sa.Column('content_hash', sa.String(length=64), nullable=False, server_default=''),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_sources')),
            sa.UniqueConstraint('url', name=op.f('uq_sources_url')),
        )

    # 10. evidence
    if not _table_exists(inspector, 'evidence'):
        op.create_table(
            'evidence',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('source_id', sa.String(length=36), nullable=False),
            sa.Column('extracted_claim', sa.Text(), nullable=False),
            sa.Column('relevance', sa.Float(), nullable=False, server_default='0.5'),
            sa.Column('confidence', sa.Float(), nullable=False, server_default='0.5'),
            sa.Column('associated_skill_names_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['source_id'], ['sources.id'],
                name=op.f('fk_evidence_source_id_sources'),
                ondelete='CASCADE',
            ),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_evidence')),
        )

    # 11. research_runs
    if not _table_exists(inspector, 'research_runs'):
        op.create_table(
            'research_runs',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('profile_id', sa.String(length=36), nullable=False),
            sa.Column('topic', sa.String(length=500), nullable=False),
            sa.Column('target_market', sa.String(length=200), nullable=False, server_default=''),
            sa.Column('status', sa.String(length=30), nullable=False, server_default='completed'),
            sa.Column('source_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('evidence_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('queries_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('errors_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('started_at', sa.DateTime(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ['profile_id'], ['user_profiles.id'],
                name=op.f('fk_research_runs_profile_id_user_profiles'),
                ondelete='CASCADE',
            ),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_research_runs')),
        )

    # 12. recommendations
    if not _table_exists(inspector, 'recommendations'):
        op.create_table(
            'recommendations',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('skill_id', sa.String(length=36), nullable=False),
            sa.Column('roadmap_id', sa.String(length=36), nullable=False),
            sa.Column('decision', sa.String(length=20), nullable=False),
            sa.Column('reasoning', sa.Text(), nullable=False),
            sa.Column('decision_factors_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('evidence_ids_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('confidence', sa.Float(), nullable=False, server_default='0.5'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['roadmap_id'], ['roadmaps.id'],
                name=op.f('fk_recommendations_roadmap_id_roadmaps'),
                ondelete='CASCADE',
            ),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_recommendations')),
        )

    # 13. progress_records
    if not _table_exists(inspector, 'progress_records'):
        op.create_table(
            'progress_records',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('profile_id', sa.String(length=36), nullable=False),
            sa.Column('skill_id', sa.String(length=36), nullable=False),
            sa.Column('skill_name', sa.String(length=200), nullable=False, server_default=''),
            sa.Column('completion_percentage', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=False, server_default=''),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ['profile_id'], ['user_profiles.id'],
                name=op.f('fk_progress_records_profile_id_user_profiles'),
                ondelete='CASCADE',
            ),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_progress_records')),
        )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table('progress_records')
    op.drop_table('recommendations')
    op.drop_table('research_runs')
    op.drop_table('evidence')
    op.drop_table('sources')
    op.drop_table('projects')
    op.drop_table('learning_resources')
    op.drop_table('milestones')
    op.drop_table('roadmap_phases')
    op.drop_table('roadmaps')
    op.drop_table('skill_dependencies')
    op.drop_table('skills')
    op.drop_table('user_profiles')
