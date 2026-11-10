"""Esquema inicial RunSense AI (26 tablas + 6 tipos ENUM).

Generada frozen a partir de app.models (Base.metadata) con dialecto PostgreSQL.
Incluye: usuarios/roles, perfiles, dispositivos, actividades + muestras,
recuperacion, objetivos, predicciones/capacidad/anomalias/recomendaciones,
versiones de modelos, escenarios y auditoria.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None
activitytype = postgresql.ENUM('RUN', 'TRAIL_RUN', 'TREADMILL', 'RACE', 'INTERVAL', 'RECOVERY_RUN', 'OTHER', name='activitytype', create_type=False)
experiencelevel = postgresql.ENUM('BEGINNER', 'INTERMEDIATE', 'ADVANCED', 'ELITE', name='experiencelevel', create_type=False)
fileformat = postgresql.ENUM('FIT', 'GPX', 'TCX', 'CSV', name='fileformat', create_type=False)
importstatus = postgresql.ENUM('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'DUPLICATE', name='importstatus', create_type=False)
metricsource = postgresql.ENUM('DEVICE', 'USER_INPUT', 'ESTIMATED', 'SYNTHETIC', name='metricsource', create_type=False)
predictionstatus = postgresql.ENUM('PENDING', 'COMPLETED', 'FAILED', 'INSUFFICIENT_DATA', name='predictionstatus', create_type=False)
ALL_ENUMS = [activitytype, experiencelevel, fileformat, importstatus, metricsource, predictionstatus]


def upgrade() -> None:
    for enum_type in ALL_ENUMS:
        enum_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        'permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False, unique=True),
        sa.Column('description', sa.String()),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False, unique=True),
        sa.Column('description', sa.String()),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=200)),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_verified', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.Column('last_login', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=100)),
        sa.Column('resource_id', sa.String(length=100)),
        sa.Column('ip_address', sa.String(length=45)),
        sa.Column('user_agent', sa.String()),
        sa.Column('extra_data', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'], unique=False)
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'], unique=False)
    op.create_table(
        'role_permissions',
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('permission_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True, nullable=False),
    )
    op.create_table(
        'runner_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('age', sa.Integer()),
        sa.Column('weight_kg', sa.Float()),
        sa.Column('height_cm', sa.Float()),
        sa.Column('experience_level', postgresql.ENUM('BEGINNER', 'INTERMEDIATE', 'ADVANCED', 'ELITE', name='experiencelevel', create_type=False)),
        sa.Column('experience_years', sa.Integer()),
        sa.Column('primary_goal', sa.String(length=200)),
        sa.Column('typical_distances', postgresql.JSONB()),
        sa.Column('training_days_per_week', sa.Integer()),
        sa.Column('bio', sa.String()),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_runner_profiles_user_id', 'runner_profiles', ['user_id'], unique=True)
    op.create_table(
        'user_roles',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True, nullable=False),
    )
    op.create_table(
        'consent_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('runner_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runner_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('granted', sa.Boolean()),
        sa.Column('granted_at', sa.DateTime(timezone=True)),
        sa.Column('revoked_at', sa.DateTime(timezone=True)),
        sa.Column('ip_address', sa.String(length=45)),
        sa.Column('notes', sa.String()),
    )
    op.create_index('ix_consent_records_runner_profile_id', 'consent_records', ['runner_profile_id'], unique=False)
    op.create_table(
        'data_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('runner_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runner_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_name', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean()),
        sa.Column('last_sync', sa.DateTime(timezone=True)),
        sa.Column('config', postgresql.JSONB()),
        sa.Column('notes', sa.String()),
        sa.Column('created_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_data_sources_runner_profile_id', 'data_sources', ['runner_profile_id'], unique=False)
    op.create_table(
        'devices',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('runner_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runner_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('brand', sa.String(length=100)),
        sa.Column('model', sa.String(length=100)),
        sa.Column('device_type', sa.String(length=50)),
        sa.Column('serial_number', sa.String(length=200)),
        sa.Column('is_active', sa.Boolean()),
        sa.Column('added_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_devices_runner_profile_id', 'devices', ['runner_profile_id'], unique=False)
    op.create_table(
        'imported_files',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('runner_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runner_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('original_filename', sa.String(length=500), nullable=False),
        sa.Column('file_format', postgresql.ENUM('FIT', 'GPX', 'TCX', 'CSV', name='fileformat', create_type=False), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger()),
        sa.Column('file_hash_sha256', sa.String(length=64)),
        sa.Column('storage_path', sa.String(length=1000)),
        sa.Column('import_status', postgresql.ENUM('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'DUPLICATE', name='importstatus', create_type=False)),
        sa.Column('error_message', sa.String()),
        sa.Column('imported_at', sa.DateTime(timezone=True)),
        sa.Column('processed_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_imported_files_file_hash_sha256', 'imported_files', ['file_hash_sha256'], unique=False)
    op.create_index('ix_imported_files_runner_profile_id', 'imported_files', ['runner_profile_id'], unique=False)
    op.create_table(
        'model_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('algorithm', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean()),
        sa.Column('is_global', sa.Boolean()),
        sa.Column('runner_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runner_profiles.id', ondelete='SET NULL')),
        sa.Column('file_path', sa.String(length=1000)),
        sa.Column('training_samples', sa.Integer()),
        sa.Column('feature_names', postgresql.JSONB()),
        sa.Column('hyperparameters', postgresql.JSONB()),
        sa.Column('trained_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True)),
    )
    op.create_table(
        'recovery_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('runner_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runner_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('metric_date', sa.Date(), nullable=False),
        sa.Column('resting_heart_rate_bpm', sa.Float()),
        sa.Column('hrv_ms', sa.Float()),
        sa.Column('recovery_score', sa.Float()),
        sa.Column('source', sa.String(length=50)),
        sa.Column('notes', sa.String()),
        sa.Column('created_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_recovery_metrics_runner_profile_id', 'recovery_metrics', ['runner_profile_id'], unique=False)
    op.create_index('ix_recovery_runner_date', 'recovery_metrics', ['runner_profile_id', 'metric_date'], unique=False)
    op.create_table(
        'simulation_scenarios',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('runner_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runner_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=200)),
        sa.Column('scenario_config', postgresql.JSONB(), nullable=False),
        sa.Column('result', postgresql.JSONB()),
        sa.Column('warnings', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_simulation_scenarios_runner_profile_id', 'simulation_scenarios', ['runner_profile_id'], unique=False)
    op.create_table(
        'sleep_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('runner_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runner_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sleep_date', sa.Date(), nullable=False),
        sa.Column('sleep_hours', sa.Float()),
        sa.Column('sleep_quality_score', sa.Float()),
        sa.Column('source', sa.String(length=50)),
        sa.Column('notes', sa.String()),
        sa.Column('created_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_sleep_records_runner_profile_id', 'sleep_records', ['runner_profile_id'], unique=False)
    op.create_index('ix_sleep_runner_date', 'sleep_records', ['runner_profile_id', 'sleep_date'], unique=False)
    op.create_table(
        'training_goals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('runner_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runner_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('goal_type', sa.String(length=50), nullable=False),
        sa.Column('target_distance_km', sa.Float()),
        sa.Column('target_time_seconds', sa.Float()),
        sa.Column('target_pace_sec_per_km', sa.Float()),
        sa.Column('target_date', sa.Date()),
        sa.Column('description', sa.String()),
        sa.Column('is_active', sa.Boolean()),
        sa.Column('achieved', sa.Boolean()),
        sa.Column('achieved_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_training_goals_runner_profile_id', 'training_goals', ['runner_profile_id'], unique=False)
    op.create_table(
        'training_loads',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('runner_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runner_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('load_date', sa.Date(), nullable=False),
        sa.Column('acute_load_7d', sa.Float()),
        sa.Column('chronic_load_28d', sa.Float()),
        sa.Column('acwr', sa.Float()),
        sa.Column('monotony', sa.Float()),
        sa.Column('strain', sa.Float()),
        sa.Column('calculated_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_training_load_runner_date', 'training_loads', ['runner_profile_id', 'load_date'], unique=False)
    op.create_index('ix_training_loads_runner_profile_id', 'training_loads', ['runner_profile_id'], unique=False)
    op.create_table(
        'activities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('runner_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runner_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('imported_file_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('imported_files.id', ondelete='SET NULL')),
        sa.Column('activity_type', postgresql.ENUM('RUN', 'TRAIL_RUN', 'TREADMILL', 'RACE', 'INTERVAL', 'RECOVERY_RUN', 'OTHER', name='activitytype', create_type=False)),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True)),
        sa.Column('timezone_name', sa.String(length=50)),
        sa.Column('title', sa.String(length=300)),
        sa.Column('notes', sa.String()),
        sa.Column('is_demo', sa.Boolean()),
        sa.Column('created_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_activities_runner_profile_id', 'activities', ['runner_profile_id'], unique=False)
    op.create_index('ix_activities_runner_started', 'activities', ['runner_profile_id', 'started_at'], unique=False)
    op.create_table(
        'capacity_estimates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('runner_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runner_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('best_pace_5k_sec_per_km', sa.Float()),
        sa.Column('best_pace_10k_sec_per_km', sa.Float()),
        sa.Column('best_pace_half_marathon_sec_per_km', sa.Float()),
        sa.Column('aerobic_threshold_pace_sec_per_km', sa.Float()),
        sa.Column('estimated_vo2max', sa.Float()),
        sa.Column('explanatory_factors', postgresql.JSONB()),
        sa.Column('warnings', postgresql.JSONB()),
        sa.Column('model_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('model_versions.id', ondelete='SET NULL')),
        sa.Column('generated_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_capacity_estimates_runner_profile_id', 'capacity_estimates', ['runner_profile_id'], unique=False)
    op.create_table(
        'model_evaluations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('model_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('model_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('mae', sa.Float()),
        sa.Column('rmse', sa.Float()),
        sa.Column('r2', sa.Float()),
        sa.Column('precision', sa.Float()),
        sa.Column('recall', sa.Float()),
        sa.Column('f1_score', sa.Float()),
        sa.Column('extra_metrics', postgresql.JSONB()),
        sa.Column('evaluation_set_size', sa.Integer()),
        sa.Column('evaluated_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_model_evaluations_model_version_id', 'model_evaluations', ['model_version_id'], unique=False)
    op.create_table(
        'recommendations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('runner_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runner_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recommendation_type', sa.String(length=100), nullable=False),
        sa.Column('priority', sa.String(length=20)),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('explanation', sa.String(), nullable=False),
        sa.Column('supporting_data', postgresql.JSONB()),
        sa.Column('is_read', sa.Boolean()),
        sa.Column('is_dismissed', sa.Boolean()),
        sa.Column('model_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('model_versions.id', ondelete='SET NULL')),
        sa.Column('generated_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_recommendations_runner_profile_id', 'recommendations', ['runner_profile_id'], unique=False)
    op.create_table(
        'activity_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('activity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('distance_meters', sa.Float()),
        sa.Column('duration_seconds', sa.Float()),
        sa.Column('avg_pace_sec_per_km', sa.Float()),
        sa.Column('avg_speed_kmh', sa.Float()),
        sa.Column('avg_heart_rate_bpm', sa.Float()),
        sa.Column('max_heart_rate_bpm', sa.Float()),
        sa.Column('avg_cadence_spm', sa.Float()),
        sa.Column('elevation_gain_meters', sa.Float()),
        sa.Column('elevation_loss_meters', sa.Float()),
        sa.Column('avg_altitude_meters', sa.Float()),
        sa.Column('training_load', sa.Float()),
        sa.Column('perceived_effort', sa.Integer()),
        sa.Column('distance_source', postgresql.ENUM('DEVICE', 'USER_INPUT', 'ESTIMATED', 'SYNTHETIC', name='metricsource', create_type=False)),
        sa.Column('heart_rate_source', postgresql.ENUM('DEVICE', 'USER_INPUT', 'ESTIMATED', 'SYNTHETIC', name='metricsource', create_type=False)),
        sa.Column('cadence_source', postgresql.ENUM('DEVICE', 'USER_INPUT', 'ESTIMATED', 'SYNTHETIC', name='metricsource', create_type=False)),
        sa.Column('raw_data', postgresql.JSONB()),
    )
    op.create_index('ix_activity_metrics_activity_id', 'activity_metrics', ['activity_id'], unique=True)
    op.create_table(
        'anomaly_detections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('runner_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runner_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('activity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('activities.id', ondelete='SET NULL')),
        sa.Column('anomaly_type', sa.String(length=100), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('description', sa.String()),
        sa.Column('context', sa.String()),
        sa.Column('method_used', sa.String(length=100)),
        sa.Column('is_acknowledged', sa.Boolean()),
        sa.Column('model_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('model_versions.id', ondelete='SET NULL')),
        sa.Column('detected_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_anomaly_detections_runner_profile_id', 'anomaly_detections', ['runner_profile_id'], unique=False)
    op.create_table(
        'heart_rate_samples',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('activity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('elapsed_seconds', sa.Float(), nullable=False),
        sa.Column('heart_rate_bpm', sa.Integer(), nullable=False),
    )
    op.create_index('ix_heart_rate_samples_activity_id', 'heart_rate_samples', ['activity_id'], unique=False)
    op.create_index('ix_hr_samples_activity_elapsed', 'heart_rate_samples', ['activity_id', 'elapsed_seconds'], unique=False)
    op.create_table(
        'pace_samples',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('activity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('elapsed_seconds', sa.Float(), nullable=False),
        sa.Column('pace_sec_per_km', sa.Float()),
        sa.Column('distance_meters', sa.Float()),
    )
    op.create_index('ix_pace_samples_activity_elapsed', 'pace_samples', ['activity_id', 'elapsed_seconds'], unique=False)
    op.create_index('ix_pace_samples_activity_id', 'pace_samples', ['activity_id'], unique=False)
    op.create_table(
        'performance_predictions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('runner_profile_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runner_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('activity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('activities.id', ondelete='SET NULL')),
        sa.Column('target_distance_km', sa.Float(), nullable=False),
        sa.Column('predicted_time_seconds', sa.Float()),
        sa.Column('predicted_pace_sec_per_km', sa.Float()),
        sa.Column('uncertainty_lower_seconds', sa.Float()),
        sa.Column('uncertainty_upper_seconds', sa.Float()),
        sa.Column('confidence_level', sa.Float()),
        sa.Column('model_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('model_versions.id', ondelete='SET NULL')),
        sa.Column('training_samples_used', sa.Integer()),
        sa.Column('is_extrapolation', sa.Boolean()),
        sa.Column('explanatory_factors', postgresql.JSONB()),
        sa.Column('warnings', postgresql.JSONB()),
        sa.Column('status', postgresql.ENUM('PENDING', 'COMPLETED', 'FAILED', 'INSUFFICIENT_DATA', name='predictionstatus', create_type=False)),
        sa.Column('correlation_id', sa.String(length=100)),
        sa.Column('generated_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_performance_predictions_runner_profile_id', 'performance_predictions', ['runner_profile_id'], unique=False)


def downgrade() -> None:
    op.drop_table('performance_predictions')
    op.drop_table('pace_samples')
    op.drop_table('heart_rate_samples')
    op.drop_table('anomaly_detections')
    op.drop_table('activity_metrics')
    op.drop_table('recommendations')
    op.drop_table('model_evaluations')
    op.drop_table('capacity_estimates')
    op.drop_table('activities')
    op.drop_table('training_loads')
    op.drop_table('training_goals')
    op.drop_table('sleep_records')
    op.drop_table('simulation_scenarios')
    op.drop_table('recovery_metrics')
    op.drop_table('model_versions')
    op.drop_table('imported_files')
    op.drop_table('devices')
    op.drop_table('data_sources')
    op.drop_table('consent_records')
    op.drop_table('user_roles')
    op.drop_table('runner_profiles')
    op.drop_table('role_permissions')
    op.drop_table('audit_logs')
    op.drop_table('users')
    op.drop_table('roles')
    op.drop_table('permissions')
    for enum_type in reversed(ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
