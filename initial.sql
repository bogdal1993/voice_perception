
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
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: vp; Owner: -
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
