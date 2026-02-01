
CREATE SCHEMA vp;


SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: calls; Type: TABLE; Schema: vp; Owner: -
--

CREATE TABLE vp.calls (
    call_uuid uuid NOT NULL,
    call_start_ts timestamp with time zone,
    call_end_ts timestamp with time zone,
    caller character varying,
    calle character varying,
    duration integer,
    direction character varying
);


--
-- Name: calls_meta; Type: TABLE; Schema: vp; Owner: -
--

CREATE TABLE vp.calls_meta (
    call_uuid uuid NOT NULL,
    meta jsonb
);


--
-- Name: calls_transcription; Type: TABLE; Schema: vp; Owner: -
--

CREATE TABLE vp.calls_transcription (
    call_uuid uuid NOT NULL,
    transcription jsonb
);


--
-- Name: files; Type: TABLE; Schema: vp; Owner: -
--

CREATE TABLE vp.files (
    call_uuid uuid NOT NULL,
    file_server character varying,
    file_path text,
    num_channels smallint
);


--
-- Name: tasks; Type: TABLE; Schema: vp; Owner: -
--

CREATE TABLE vp.tasks (
    call_uuid uuid NOT NULL,
    task jsonb
);


--
-- Name: transcript_queue; Type: TABLE; Schema: vp; Owner: -
--

CREATE TABLE vp.transcript_queue (
    file_server character varying,
    file_path text,
    status character varying,
    call_uuid uuid NOT NULL
);

CREATE TABLE IF NOT EXISTS vp.calls_tags
(
    call_uuid uuid NOT NULL,
    tags_json jsonb,
    CONSTRAINT calls_tags_pkey PRIMARY KEY (call_uuid)
);

CREATE TABLE IF NOT EXISTS vp.tags_core
(
    tag_id serial,
    tag_name character varying NOT NULL,
    tag_spk integer NOT NULL,
    tag_texts jsonb,
    CONSTRAINT tags_core_pkey PRIMARY KEY (tag_id)
);


--
-- Authentication tables for mentor mode
--

-- Table for mentors (users from htpasswd)
CREATE TABLE vp.mentors (
    mentor_id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- Table for mentor access to specific phone numbers
CREATE TABLE vp.mentor_phone_access (
    access_id SERIAL PRIMARY KEY,
    mentor_id INTEGER NOT NULL REFERENCES vp.mentors(mentor_id) ON DELETE CASCADE,
    phone_number VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(mentor_id, phone_number)
);

CREATE TABLE IF NOT EXISTS vp.api_keys
(
    api_key_id SERIAL PRIMARY KEY,
    mentor_id INTEGER NOT NULL REFERENCES vp.mentors(mentor_id) ON DELETE CASCADE,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    key_prefix VARCHAR(16) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for faster lookups
CREATE INDEX idx_mentor_phone_access_mentor ON vp.mentor_phone_access(mentor_id);
CREATE INDEX idx_mentor_phone_access_phone ON vp.mentor_phone_access(phone_number);
CREATE INDEX idx_mentors_username ON vp.mentors(username);
CREATE INDEX idx_mentors_role ON vp.mentors(role);
CREATE INDEX idx_api_keys_mentor_id ON vp.api_keys(mentor_id);
CREATE INDEX idx_api_keys_key_hash ON vp.api_keys(key_hash);

-- Table for metadata mapping configurations
-- This table stores how JSON keys from calls_meta should be mapped to display names and types in the UI
CREATE TABLE vp.metadata_mappings (
    mapping_id SERIAL PRIMARY KEY,
    field_key VARCHAR(255) NOT NULL,           -- The JSON key from calls_meta.meta
    display_name VARCHAR(255) NOT NULL,        -- The display name shown in the UI
    field_type VARCHAR(100) NOT NULL,          -- The data type (text, number, date, boolean, etc.)
    is_active BOOLEAN DEFAULT true,            -- Whether this mapping is currently active
    sort_order INTEGER DEFAULT 0,              -- Order in which fields should appear in UI
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES vp.mentors(mentor_id),  -- Reference to admin who created the mapping
    description TEXT                           -- Optional description of what this field represents
);

-- Indexes for metadata mappings table
CREATE INDEX idx_metadata_mappings_field_key ON vp.metadata_mappings(field_key);
CREATE INDEX idx_metadata_mappings_is_active ON vp.metadata_mappings(is_active);
CREATE INDEX idx_metadata_mappings_sort_order ON vp.metadata_mappings(sort_order);


--
-- Name: calls_meta calls_meta_pkey; Type: CONSTRAINT; Schema: vp; Owner: -
--

ALTER TABLE ONLY vp.calls_meta
    ADD CONSTRAINT calls_meta_pkey PRIMARY KEY (call_uuid);


--
-- Name: calls calls_pkey; Type: CONSTRAINT; Schema: vp; Owner: -
--

ALTER TABLE ONLY vp.calls
    ADD CONSTRAINT calls_pkey PRIMARY KEY (call_uuid);


--
-- Name: calls_transcription calls_transcription_pkey; Type: CONSTRAINT; Schema: vp; Owner: -
--

ALTER TABLE ONLY vp.calls_transcription
    ADD CONSTRAINT calls_transcription_pkey PRIMARY KEY (call_uuid);


--
-- Name: files files_pkey; Type: CONSTRAINT; Schema: vp; Owner: -
--

ALTER TABLE ONLY vp.files
    ADD CONSTRAINT files_pkey PRIMARY KEY (call_uuid);


--
-- Name: tasks_pkey; Type: CONSTRAINT; Schema: vp; Owner: -
--

ALTER TABLE ONLY vp.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (call_uuid);


--
-- Name: transcript_queue transcript_queue_pkey; Type: CONSTRAINT; Schema: vp; Owner: -
--

ALTER TABLE ONLY vp.transcript_queue
    ADD CONSTRAINT transcript_queue_pkey PRIMARY KEY (call_uuid);


--
-- PostgreSQL database dump complete
--
