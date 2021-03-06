# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

forward_create_tables = """

    -- A utility function we need, from:
    -- https://wiki.postgresql.org/wiki/Unnest_multidimensional_array
    CREATE OR REPLACE FUNCTION reduce_dim(anyarray)
    RETURNS SETOF anyarray AS
    $function$
    DECLARE
        s $1%TYPE;
    BEGIN
        FOREACH s SLICE 1  IN ARRAY $1 LOOP
            RETURN NEXT s;
        END LOOP;
        RETURN;
    END;
    $function$
    LANGUAGE plpgsql IMMUTABLE;

    CREATE TABLE point_set (
        id int GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        user_id int REFERENCES auth_user(id) ON DELETE CASCADE NOT NULL,
        project_id int REFERENCES project(id) ON DELETE CASCADE NOT NULL,
        creation_time timestamptz NOT NULL DEFAULT now(),
        edition_time timestamptz NOT NULL DEFAULT now(),
        name text NOT NULL,
        description text,
        txid bigint DEFAULT txid_current(),
        -- Convention: an array of flattened points. Each sub-array
        -- represents one point set, with its points stored in the
        -- form [X, Y, Z, X, Y, Z, …]. This general pattern is enforced with a
        -- CHECK constraint.
        points real[] CHECK (CARDINALITY(points) % 3 = 0) NOT NULL
    );

    CREATE TABLE nblast_sample (
        id int GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        user_id int REFERENCES auth_user(id) ON DELETE CASCADE NOT NULL,
        project_id int REFERENCES project(id) ON DELETE CASCADE NOT NULL,
        creation_time timestamptz NOT NULL DEFAULT now(),
        edition_time timestamptz NOT NULL DEFAULT now(),
        name text,
        -- Referential integretry is not needed here. We don't want sample to be
        -- deleted if a neuron is deleted that is used as sample.
        sample_neurons bigint[],
        sample_pointclouds bigint[],
        sample_pointsets bigint[],
        histogram int[][],
        probability real[][],
        txid bigint DEFAULT txid_current()
    );

    CREATE TABLE nblast_config (
        id int GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        user_id int REFERENCES auth_user(id) ON DELETE CASCADE NOT NULL,
        project_id int REFERENCES project(id) ON DELETE CASCADE NOT NULL,
        creation_time timestamptz NOT NULL DEFAULT now(),
        edition_time timestamptz NOT NULL DEFAULT now(),
        name text NOT NULL,
        status text CHECK (status IN ('queued', 'computing', 'complete', 'error')),
        distance_breaks float[] NOT NULL,
        dot_breaks float[] NOT NULL,
        resample_step float default 1000 NOT NULL,
        tangent_neighbors int default 20 NOT NULL,
        match_sample_id int REFERENCES nblast_sample(id),
        random_sample_id int REFERENCES nblast_sample(id),
        scoring float[][],
        txid bigint DEFAULT txid_current()
    );

    CREATE TABLE nblast_skeleton_source_type (
        name text NOT NULL PRIMARY KEY,
        description text NOT NULL
    );

    CREATE TABLE nblast_similarity (
        id int GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        user_id int REFERENCES auth_user(id) ON DELETE CASCADE NOT NULL,
        project_id int REFERENCES project(id) ON DELETE CASCADE NOT NULL,
        creation_time timestamptz NOT NULL DEFAULT now(),
        edition_time timestamptz NOT NULL DEFAULT now(),
        status text CHECK (status IN ('queued', 'computing', 'complete', 'error')),
        name text NOT NULL,
        config_id integer REFERENCES nblast_config(id) ON DELETE CASCADE NOT NULL,
        query_type_id text REFERENCES nblast_skeleton_source_type(name) NOT NULL,
        target_type_id text REFERENCES nblast_skeleton_source_type(name) NOT NULL,
        scoring real[][],
        txid bigint DEFAULT txid_current(),
        query_objects bigint[],
        target_objects bigint[]
    );

    CREATE TABLE pointcloud (
        id int GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        user_id int REFERENCES auth_user(id) ON DELETE CASCADE NOT NULL,
        project_id int REFERENCES project(id) ON DELETE CASCADE NOT NULL,
        creation_time timestamptz NOT NULL DEFAULT now(),
        edition_time timestamptz NOT NULL DEFAULT now(),
        name text NOT NULL,
        description text NOT NULL DEFAULT '',
        source_path text NOT NULL DEFAULT '',
        txid bigint DEFAULT txid_current()
    );

    CREATE TABLE pointcloud_point (
        id int GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        project_id int REFERENCES project(id) ON DELETE CASCADE NOT NULL,
        pointcloud_id int REFERENCES pointcloud(id) ON DELETE CASCADE NOT NULL,
        point_id bigint REFERENCES point(id) ON DELETE CASCADE NOT NULL,
        edition_time timestamptz NOT NULL DEFAULT now(),
        txid bigint DEFAULT txid_current()
    );

    CREATE TABLE image_data (
        id int GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        user_id int REFERENCES auth_user(id) ON DELETE CASCADE NOT NULL,
        project_id int REFERENCES project(id) ON DELETE CASCADE NOT NULL,
        creation_time timestamptz NOT NULL DEFAULT now(),
        edition_time timestamptz NOT NULL DEFAULT now(),
        name text NOT NULL,
        description text NOT NULL DEFAULT '',
        source_path text NOT NULL DEFAULT '',
        content_type text NOT NULL,
        image bytea NOT NULL,
        txid bigint DEFAULT txid_current()
    );

    CREATE TABLE pointcloud_image_data (
        id int GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
        project_id int REFERENCES project(id) ON DELETE CASCADE NOT NULL,
        pointcloud_id int REFERENCES pointcloud(id) ON DELETE CASCADE NOT NULL,
        image_data_id int REFERENCES image_data(id) ON DELETE CASCADE NOT NULL,
        txid bigint DEFAULT txid_current()
    );


    -- Create basic source types
    INSERT INTO nblast_skeleton_source_type (name, description)
    VALUES ('skeleton', 'Regular skeleton'),
           ('pointcloud', 'Arbitrary point cloud'),
           ('pointset', 'Arbitrary self-contained list of points');


    -- Create indexes
    CREATE INDEX point_set_id_idx ON point_set USING btree (id);
    CREATE INDEX point_set_project_id_idx ON point_set USING btree (project_id);

    CREATE INDEX nblast_sample_id_idx ON nblast_sample USING btree (id);
    CREATE INDEX nblast_project_id_idx ON nblast_sample USING btree (project_id);

    CREATE INDEX nblast_config_id_idx ON nblast_config USING btree (id);
    CREATE INDEX nblast_config_project_id_idx ON nblast_config USING btree (project_id);

    CREATE INDEX nblast_similarity_query_objects ON nblast_similarity
        USING GIN (query_objects, target_objects);
    CREATE INDEX nblast_similarity_project_id_idx ON nblast_similarity
        USING btree (project_id);

    CREATE INDEX nblast_skeleton_source_type_name_idx ON nblast_skeleton_source_type
        USING btree (name);

    CREATE INDEX pointcloud_id_idx ON pointcloud USING btree (id);
    CREATE INDEX pointcloud_project_idx ON pointcloud USING btree (project_id);
    CREATE INDEX pointcloud_name_idx ON pointcloud USING btree (name);

    CREATE INDEX pointcloud_point_id_idx ON pointcloud_point USING btree (id);
    CREATE INDEX pointcloud_point_project_id_pointcloud_id_idx
        ON pointcloud_point USING btree (project_id, pointcloud_id);

    CREATE INDEX image_data_id_idx ON image_data USING btree (id);
    CREATE INDEX image_data_project_id_idx ON image_data USING btree (project_id);

    CREATE INDEX pointcloud_image_data_project_id_pointcloud_id_idx
        ON pointcloud_image_data USING btree (project_id, pointcloud_id);


    -- Create history tables
    SELECT create_history_table('point_set'::regclass, 'edition_time', 'txid');
    SELECT create_history_table('nblast_sample'::regclass, 'edition_time', 'txid');
    SELECT create_history_table('nblast_config'::regclass, 'edition_time', 'txid');
    SELECT create_history_table('nblast_similarity'::regclass, 'edition_time', 'txid');
    SELECT create_history_table('nblast_skeleton_source_type'::regclass);
    SELECT create_history_table('pointcloud'::regclass, 'edition_time', 'txid');
    SELECT create_history_table('pointcloud_point'::regclass, 'edition_time', 'txid');
    SELECT create_history_table('image_data'::regclass, 'edition_time', 'txid');
    SELECT create_history_table('pointcloud_image_data'::regclass);
"""

backward_create_tables = """
    SELECT drop_history_table('point_set'::regclass);
    SELECT drop_history_table('nblast_sample'::regclass);
    SELECT drop_history_table('nblast_config'::regclass);
    SELECT drop_history_table('nblast_similarity'::regclass);
    SELECT drop_history_table('nblast_skeleton_source_type'::regclass);
    SELECT drop_history_table('pointcloud'::regclass);
    SELECT drop_history_table('pointcloud_point'::regclass);
    SELECT drop_history_table('image_data'::regclass);
    SELECT drop_history_table('pointcloud_image_data'::regclass);

    DROP TABLE pointcloud_image_data;
    DROP TABLE image_data;
    DROP TABLE pointcloud_point;
    DROP TABLE pointcloud;
    DROP TABLE nblast_similarity;
    DROP TABLE nblast_config;
    DROP TABLE nblast_sample;
    DROP TABLE nblast_skeleton_source_type;
    DROP TABLE point_set;

    DROP FUNCTION reduce_dim(anyarray);
"""

class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('catmaid', '0046_add_can_queue_compute_task_permission'),
    ]

    operations = [
        migrations.RunSQL(
            forward_create_tables,
            backward_create_tables,
            [
                migrations.CreateModel(
                    name='PointSet',
                    fields=[
                        ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('creation_time', models.DateTimeField(default=django.utils.timezone.now)),
                        ('edition_time', models.DateTimeField(default=django.utils.timezone.now)),
                        ('name', models.TextField()),
                        ('description', models.TextField()),
                        ('points', django.contrib.postgres.fields.ArrayField(base_field=models.FloatField(), size=None)),
                    ],
                    options={
                        'db_table': 'point_set',
                    },
                ),
                migrations.CreateModel(
                    name='ImageData',
                    fields=[
                        ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('creation_time', models.DateTimeField(default=django.utils.timezone.now)),
                        ('edition_time', models.DateTimeField(default=django.utils.timezone.now)),
                        ('name', models.TextField()),
                        ('description', models.TextField(default='')),
                        ('source_path', models.TextField(default='')),
                        ('content_type', models.TextField()),
                        ('image', models.BinaryField()),
                    ],
                    options={
                        'db_table': 'image_data',
                    },
                ),
                migrations.CreateModel(
                    name='NblastConfig',
                    fields=[
                        ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('creation_time', models.DateTimeField(default=django.utils.timezone.now)),
                        ('edition_time', models.DateTimeField(default=django.utils.timezone.now)),
                        ('name', models.TextField()),
                        ('status', models.TextField()),
                        ('distance_breaks', django.contrib.postgres.fields.ArrayField(base_field=models.FloatField(default=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]), size=None)),
                        ('dot_breaks', django.contrib.postgres.fields.ArrayField(base_field=models.FloatField(default=(0, 0.75, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 20, 25, 30, 40, 500)), size=None)),
                        ('scoring', django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.FloatField(), size=None), size=None)),
                        ('resample_step', models.FloatField(default=1000)),
                        ('tangent_neighbors', models.IntegerField(default=5)),
                    ],
                    options={
                        'db_table': 'nblast_config',
                    },
                ),
                migrations.CreateModel(
                    name='NblastSample',
                    fields=[
                        ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('creation_time', models.DateTimeField(default=django.utils.timezone.now)),
                        ('edition_time', models.DateTimeField(default=django.utils.timezone.now)),
                        ('name', models.TextField()),
                        ('sample_neurons', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), size=None)),
                        ('histogram', django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), size=None), size=None)),
                        ('probability', django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.FloatField(), size=None), size=None)),
                    ],
                    options={
                        'db_table': 'nblast_sample',
                    },
                ),
                migrations.CreateModel(
                    name='NblastSimilarity',
                    fields=[
                        ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('creation_time', models.DateTimeField(default=django.utils.timezone.now)),
                        ('edition_time', models.DateTimeField(default=django.utils.timezone.now)),
                        ('name', models.TextField()),
                        ('status', models.TextField()),
                        ('scoring', django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.FloatField(), size=None), size=None)),
                        ('query_objects', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), size=None)),
                        ('target_objects', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), size=None)),
                        ('config', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='catmaid.NblastConfig')),
                    ],
                    options={
                        'db_table': 'nblast_similarity',
                    },
                ),
                migrations.CreateModel(
                    name='NblastSkeletonSourceType',
                    fields=[
                        ('name', models.TextField(primary_key=True, serialize=False)),
                        ('description', models.TextField(default='')),
                    ],
                    options={
                        'db_table': 'nblast_skeleton_source_type',
                    },
                ),
                migrations.CreateModel(
                    name='PointCloud',
                    fields=[
                        ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('creation_time', models.DateTimeField(default=django.utils.timezone.now)),
                        ('edition_time', models.DateTimeField(default=django.utils.timezone.now)),
                        ('name', models.TextField()),
                        ('description', models.TextField(default='')),
                        ('source_path', models.TextField(default='')),
                    ],
                    options={
                        'db_table': 'pointcloud',
                    },
                ),
                migrations.CreateModel(
                    name='PointCloudImageData',
                    fields=[
                        ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('image_data', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='catmaid.ImageData')),
                        ('pointcloud', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='catmaid.PointCloud')),
                    ],
                    options={
                        'db_table': 'pointcloud_image_data',
                    },
                ),
                migrations.CreateModel(
                    name='PointCloudPoint',
                    fields=[
                        ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('point', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='catmaid.Point')),
                        ('pointcloud', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='catmaid.PointCloud')),
                    ],
                    options={
                        'db_table': 'pointcloud_point',
                    },
                ),
                migrations.AddField(
                    model_name='pointcloudpoint',
                    name='project',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='catmaid.Project'),
                ),
                migrations.AddField(
                    model_name='pointcloudimagedata',
                    name='project',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='catmaid.Project'),
                ),
                migrations.AddField(
                    model_name='pointcloud',
                    name='project',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='catmaid.Project'),
                ),
                migrations.AddField(
                    model_name='pointcloud',
                    name='images',
                    field=models.ManyToManyField(through='catmaid.PointCloudImageData', to='catmaid.ImageData'),
                ),
                migrations.AddField(
                    model_name='pointcloud',
                    name='points',
                    field=models.ManyToManyField(through='catmaid.PointCloudPoint', to='catmaid.Point'),
                ),
                migrations.AddField(
                    model_name='pointcloud',
                    name='user',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL),
                ),
                migrations.AddField(
                    model_name='pointset',
                    name='project',
                    field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.DO_NOTHING, to='catmaid.Project'),
                    preserve_default=False,
                ),
                migrations.AddField(
                    model_name='pointset',
                    name='user',
                    field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL),
                    preserve_default=False,
                ),
                migrations.AddField(
                    model_name='nblastsimilarity',
                    name='project',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='catmaid.Project'),
                ),
                migrations.AddField(
                    model_name='nblastsimilarity',
                    name='query_type',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='query_type_set', to='catmaid.NblastSkeletonSourceType'),
                ),
                migrations.AddField(
                    model_name='nblastsimilarity',
                    name='target_type',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='target_type_set', to='catmaid.NblastSkeletonSourceType'),
                ),
                migrations.AddField(
                    model_name='nblastsimilarity',
                    name='user',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL),
                ),
                migrations.AddField(
                    model_name='nblastsample',
                    name='project',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='catmaid.Project'),
                ),
                migrations.AddField(
                    model_name='nblastsample',
                    name='user',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL),
                ),
                migrations.AddField(
                    model_name='nblastconfig',
                    name='match_sample',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='match_config_set', to='catmaid.NblastSample'),
                ),
                migrations.AddField(
                    model_name='nblastsample',
                    name='sample_pointclouds',
                    field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), default=1, size=None),
                    preserve_default=False,
                ),
                migrations.AddField(
                    model_name='nblastsample',
                    name='sample_pointsets',
                    field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), default=1, size=None),
                    preserve_default=False,
                ),
                migrations.AddField(
                    model_name='nblastconfig',
                    name='project',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='catmaid.Project'),
                ),
                migrations.AddField(
                    model_name='nblastconfig',
                    name='random_sample',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='random_config_set', to='catmaid.NblastSample'),
                ),
                migrations.AddField(
                    model_name='nblastconfig',
                    name='user',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL),
                ),
                migrations.AddField(
                    model_name='imagedata',
                    name='project',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='catmaid.Project'),
                ),
                migrations.AddField(
                    model_name='imagedata',
                    name='user',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL),
                ),
            ])
    ]
