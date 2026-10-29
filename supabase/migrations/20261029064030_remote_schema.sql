SET local check_function_bodies = off;

CREATE EXTENSION "btree_gist" SCHEMA "extensions";

CREATE EXTENSION "pg_cron";

CREATE SEQUENCE "public"."equipment_equipment_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE "public"."equipment_request_equipment_request_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE "public"."roles_role_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE TABLE "public"."equipment_request" (
  "equipment_request_id"   integer                  NOT NULL DEFAULT nextval('public.equipment_request_equipment_request_id_seq'::regclass),
  "event_id"               integer                  NOT NULL,
  "equipment_id"           integer,
  "requested_by"           uuid                     NOT NULL,
  "reviewed_by"            uuid,
  "quantity"               integer                  NOT NULL,
  "status"                 character varying(50)    NOT NULL DEFAULT 'pending'::character varying,
  "technical_requirements" text,
  "requested_at"           timestamp with time zone NOT NULL DEFAULT now(),
  "equipment_type"         character varying(200)   NOT NULL,
  "reason_for_rejection"   text,
  "accepted_quantity"      integer,
  "reviewed_at"            timestamp with time zone,
  CONSTRAINT "equipment_request_accepted_quantity_check" CHECK ((accepted_quantity >= 0)),
  CONSTRAINT "equipment_request_pkey" PRIMARY KEY (equipment_request_id),
  CONSTRAINT "equipment_request_quantity_check" CHECK ((quantity > 0))
);

REVOKE ALL ON TABLE "public"."equipment_request" FROM "anon";

CREATE TABLE "public"."equipment_reservations" (
  "reservation_id"       uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "event_id"             integer                  NOT NULL,
  "equipment_id"         integer                  NOT NULL,
  "quantity"             integer                  NOT NULL,
  "starts_at"            timestamp with time zone NOT NULL,
  "ends_at"              timestamp with time zone NOT NULL,
  "created_by"           uuid                     NOT NULL,
  "created_at"           timestamp with time zone NOT NULL DEFAULT now(),
  "equipment_request_id" integer,
  CONSTRAINT "equipment_reservations_check" CHECK ((ends_at > starts_at)),
  CONSTRAINT "equipment_reservations_equipment_request_id_key" UNIQUE (equipment_request_id),
  CONSTRAINT "equipment_reservations_pkey" PRIMARY KEY (reservation_id),
  CONSTRAINT "equipment_reservations_quantity_check" CHECK ((quantity > 0))
);

REVOKE ALL ON TABLE "public"."equipment_reservations" FROM "anon", "authenticated";

CREATE TABLE "public"."equipment" (
  "equipment_id"    integer                NOT NULL DEFAULT nextval('public.equipment_equipment_id_seq'::regclass),
  "equipment_type"  character varying(100) NOT NULL,
  "equipment_model" character varying(100) NOT NULL,
  "total_quantity"  integer                NOT NULL DEFAULT 0,
  CONSTRAINT "equipment_pkey" PRIMARY KEY (equipment_id),
  CONSTRAINT "equipment_total_quantity_check" CHECK ((total_quantity >= 0))
);

REVOKE ALL ON TABLE "public"."equipment" FROM "anon";

CREATE TABLE "public"."event_activity" (
  "activity_id"             bigint                   GENERATED ALWAYS AS IDENTITY NOT NULL,
  "event_id"                integer                  NOT NULL,
  "changed_by"              uuid,
  "change_type"             text                     NOT NULL,
  "changes"                 jsonb                    NOT NULL DEFAULT '{}'::jsonb,
  "created_at"              timestamp with time zone NOT NULL DEFAULT now(),
  "event_change_request_id" bigint,
  CONSTRAINT "event_activity_change_type_check" CHECK ((change_type = ANY (ARRAY['edit'::text, 'critical_edit'::text, 'status_change'::text]))),
  CONSTRAINT "event_activity_pkey" PRIMARY KEY (activity_id)
);

CREATE TABLE "public"."event_change_request" (
  "event_change_request_id" bigint  GENERATED ALWAYS AS IDENTITY NOT NULL,
  "event_id"                integer NOT NULL,
  "requested_by"            uuid    NOT NULL,
  "assigned_coordinator_id" uuid    NOT NULL,
  "reason"                  text    NOT NULL,
  "proposed_values"         jsonb   NOT NULL,
  "changes"                 jsonb   NOT NULL,
  CONSTRAINT "event_change_request_changes_check" CHECK (((jsonb_typeof(changes) = 'object'::text) AND (changes <> '{}'::jsonb))),
  CONSTRAINT "event_change_request_pkey" PRIMARY KEY (event_change_request_id),
  CONSTRAINT "event_change_request_proposed_values_check" CHECK (((jsonb_typeof(proposed_values) = 'object'::text) AND (proposed_values <> '{}'::jsonb))),
  CONSTRAINT "event_change_request_reason_check" CHECK (((NULLIF(btrim(reason), ''::text) IS NOT NULL) AND (length(reason) <= 2000)))
);

ALTER TABLE "public"."event_change_request"
  ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."event_registration" (
  "event_id"      integer                  NOT NULL,
  "attendee_id"   uuid                     NOT NULL,
  "status"        text                     NOT NULL,
  "created_at"    timestamp with time zone NOT NULL DEFAULT clock_timestamp(),
  "full_name"     text,
  "contact_email" text,
  "contact_phone" text,
  "withdrawn_at"  timestamp with time zone,
  CONSTRAINT "event_registration_pkey" PRIMARY KEY (event_id, attendee_id),
  CONSTRAINT "event_registration_status_check" CHECK ((status = ANY (ARRAY['registered'::text, 'waiting_list'::text, 'withdrawn'::text])))
);

ALTER TABLE "public"."event_registration"
  ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "public"."event_registration" FROM "anon";

CREATE TABLE "public"."event_request_amendment" (
  "amendment_id"     bigint                   GENERATED ALWAYS AS IDENTITY NOT NULL,
  "event_request_id" bigint                   NOT NULL,
  "amended_by"       uuid                     NOT NULL,
  "changes"          jsonb                    NOT NULL DEFAULT '{}'::jsonb,
  "note"             text,
  "created_at"       timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT "event_request_amendment_changes_is_object" CHECK ((jsonb_typeof(changes) = 'object'::text)),
  CONSTRAINT "event_request_amendment_pkey" PRIMARY KEY (amendment_id)
);

REVOKE ALL ON TABLE "public"."event_request_amendment" FROM "anon";

CREATE TABLE "public"."event_request_review" (
  "review_id"        bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  "event_request_id" bigint NOT NULL,
  "reviewer_id"      uuid   NOT NULL,
  CONSTRAINT "event_request_review_pkey" PRIMARY KEY (review_id)
);

REVOKE ALL ON TABLE "public"."event_request_review" FROM "anon";

CREATE TABLE "public"."event_request" (
  "event_request_id"     bigint                   GENERATED ALWAYS AS IDENTITY NOT NULL,
  "event_name"           text,
  "purpose"              text,
  "description"          text,
  "event_organiser_id"   uuid                     NOT NULL,
  "event_coordinator_id" uuid,
  "start_datetime"       timestamp with time zone,
  "end_datetime"         timestamp with time zone,
  "capacity_needed"      integer,
  CONSTRAINT "event_request_pkey" PRIMARY KEY (event_request_id),
  CONSTRAINT "positive_capacity" CHECK (((capacity_needed IS NULL) OR (capacity_needed > 0))),
  CONSTRAINT "valid_time_range" CHECK (((end_datetime IS NULL) OR (end_datetime > start_datetime)))
);

REVOKE ALL ON TABLE "public"."event_request" FROM "anon";

CREATE TABLE "public"."events" (
  "event_id"         integer                  GENERATED BY DEFAULT AS IDENTITY NOT NULL,
  "event_request_id" bigint                   NOT NULL,
  "event_name"       text                     NOT NULL,
  "purpose"          text                     NOT NULL,
  "description"      text                     NOT NULL,
  "start_datetime"   timestamp with time zone NOT NULL,
  "end_datetime"     timestamp with time zone NOT NULL,
  "capacity_needed"  integer                  NOT NULL,
  CONSTRAINT "events_capacity_needed_check" CHECK ((capacity_needed > 0)),
  CONSTRAINT "events_description_check" CHECK ((btrim(description) <> ''::text)),
  CONSTRAINT "events_event_name_check" CHECK ((btrim(event_name) <> ''::text)),
  CONSTRAINT "events_event_request_id_key" UNIQUE (event_request_id),
  CONSTRAINT "events_pkey" PRIMARY KEY (event_id),
  CONSTRAINT "events_purpose_check" CHECK ((btrim(purpose) <> ''::text)),
  CONSTRAINT "events_valid_time_range" CHECK ((end_datetime > start_datetime))
);

REVOKE ALL ON TABLE "public"."events" FROM "anon";

CREATE TABLE "public"."notifications" (
  "notification_id" bigint                   GENERATED ALWAYS AS IDENTITY NOT NULL,
  "recipient_id"    uuid                     NOT NULL,
  "kind"            text                     NOT NULL,
  "title"           text                     NOT NULL,
  "body"            text                     NOT NULL,
  "link"            text,
  "created_at"      timestamp with time zone NOT NULL DEFAULT now(),
  "read_at"         timestamp with time zone,
  CONSTRAINT "notifications_body_check" CHECK ((btrim(body) <> ''::text)),
  CONSTRAINT "notifications_kind_check" CHECK ((btrim(kind) <> ''::text)),
  CONSTRAINT "notifications_pkey" PRIMARY KEY (notification_id),
  CONSTRAINT "notifications_title_check" CHECK ((btrim(title) <> ''::text))
);

ALTER TABLE "public"."notifications"
  ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "public"."notifications" FROM "anon", "authenticated";

CREATE TABLE "public"."operational_safety_decision" (
  "safety_decision_id"    bigint                   GENERATED ALWAYS AS IDENTITY NOT NULL,
  "event_id"              integer                  NOT NULL,
  "safety_officer_id"     uuid                     NOT NULL,
  "outcome"               text                     NOT NULL,
  "remarks"               text,
  "affected_arrangements" text[]                   NOT NULL DEFAULT ARRAY[]::text[],
  "created_at"            timestamp with time zone NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT "operational_safety_decision_affected_arrangements_check" CHECK ((affected_arrangements <@ ARRAY['venue'::text, 'technical'::text])),
  CONSTRAINT "operational_safety_decision_outcome_check" CHECK ((outcome = ANY (ARRAY['approved'::text, 'rejected'::text, 'changes_requested'::text]))),
  CONSTRAINT "operational_safety_decision_pkey" PRIMARY KEY (safety_decision_id),
  CONSTRAINT "safety_decision_remarks_length" CHECK (((remarks IS NULL) OR (length(remarks) <= 2000))),
  CONSTRAINT "safety_decision_remarks_required" CHECK (((outcome = 'approved'::text) OR (NULLIF(btrim(remarks), ''::text) IS NOT NULL)))
);

REVOKE ALL ON TABLE "public"."operational_safety_decision" FROM "anon", "authenticated";

CREATE TABLE "public"."registration_email_outbox" (
  "id"          bigint                   GENERATED ALWAYS AS IDENTITY NOT NULL,
  "event_id"    integer                  NOT NULL,
  "attendee_id" uuid                     NOT NULL,
  "recipient"   text                     NOT NULL,
  "subject"     text                     NOT NULL,
  "body"        text                     NOT NULL,
  "created_at"  timestamp with time zone NOT NULL DEFAULT clock_timestamp(),
  "sent_at"     timestamp with time zone,
  CONSTRAINT "registration_email_outbox_event_id_attendee_id_key" UNIQUE (event_id, attendee_id),
  CONSTRAINT "registration_email_outbox_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."registration_email_outbox"
  ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "public"."registration_email_outbox" FROM "anon", "authenticated";

CREATE TABLE "public"."roles" (
  "role_id"   integer               NOT NULL DEFAULT nextval('public.roles_role_id_seq'::regclass),
  "role_name" character varying(50) NOT NULL,
  CONSTRAINT "roles_pkey" PRIMARY KEY (role_id)
);

CREATE TABLE "public"."user_roles" (
  "user_id" uuid    NOT NULL,
  "role_id" integer NOT NULL,
  CONSTRAINT "user_roles_pkey" PRIMARY KEY (user_id, role_id)
);

CREATE TABLE "public"."users" (
  "user_id"    uuid                     NOT NULL,
  "name"       character varying(100)   NOT NULL,
  "email"      character varying(255)   NOT NULL,
  "created_at" timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT "users_email_key" UNIQUE (email),
  CONSTRAINT "users_pkey" PRIMARY KEY (user_id)
);

REVOKE ALL ON TABLE "public"."users" FROM "anon";

CREATE TABLE "public"."venue_blocks" (
  "block_id"   uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "venue_id"   uuid                     NOT NULL,
  "starts_at"  timestamp with time zone NOT NULL,
  "ends_at"    timestamp with time zone NOT NULL,
  "reason"     text,
  "created_by" uuid,
  "created_at" timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT "venue_blocks_check" CHECK ((ends_at > starts_at)),
  CONSTRAINT "venue_blocks_pkey" PRIMARY KEY (block_id)
);

ALTER TABLE "public"."venue_blocks"
  ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "public"."venue_blocks" FROM "anon", "authenticated";

CREATE TABLE "public"."venue_booking_requests" (
  "booking_id"          uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "venue_id"            uuid                     NOT NULL,
  "requested_by"        uuid                     NOT NULL,
  "event_name"          text                     NOT NULL,
  "starts_at"           timestamp with time zone NOT NULL,
  "ends_at"             timestamp with time zone NOT NULL,
  "attendance"          integer                  NOT NULL,
  "venue_requirements"  text                     NOT NULL,
  "status"              text                     NOT NULL DEFAULT 'submitted'::text,
  "submitted_at"        timestamp with time zone NOT NULL DEFAULT now(),
  "event_id"            integer,
  "reviewed_by"         uuid,
  "reviewed_at"         timestamp with time zone,
  "review_comments"     text,
  "cancelled_at"        timestamp with time zone,
  "occupied_from"       timestamp with time zone NOT NULL,
  "occupied_until"      timestamp with time zone NOT NULL,
  "cancellation_reason" text,
  "hold_expires_at"     timestamp with time zone,
  "expired_at"          timestamp with time zone,
  CONSTRAINT "venue_booking_comments_length" CHECK (((review_comments IS NULL) OR (length(review_comments) <= 2000))),
  CONSTRAINT "venue_booking_decision_recorded"
    CHECK (((status = ANY (ARRAY['cancelled'::text, 'expired'::text])) OR ((status = 'submitted'::text) = ((reviewed_at IS NULL) AND (reviewed_by IS NULL))))),
  CONSTRAINT "venue_booking_rejection_has_reason" CHECK (((status <> 'rejected'::text) OR (length(TRIM(BOTH FROM COALESCE(review_comments, ''::text))) > 0))),
  CONSTRAINT "venue_booking_requests_attendance_check" CHECK ((attendance > 0)),
  CONSTRAINT "venue_booking_requests_check" CHECK ((ends_at > starts_at)),
  CONSTRAINT "venue_booking_requests_event_name_check" CHECK (((length(TRIM(BOTH FROM event_name)) >= 1) AND (length(TRIM(BOTH FROM event_name)) <= 200))),
  CONSTRAINT "venue_booking_requests_pkey" PRIMARY KEY (booking_id),
  CONSTRAINT "venue_booking_requests_venue_requirements_check" CHECK (((length(TRIM(BOTH FROM venue_requirements)) >= 1) AND (length(TRIM(BOTH FROM venue_requirements)) <= 5000))),
  CONSTRAINT "venue_booking_status_known" CHECK ((status = ANY (ARRAY['submitted'::text, 'approved'::text, 'rejected'::text, 'cancelled'::text, 'expired'::text])))
);

REVOKE ALL ON TABLE "public"."venue_booking_requests" FROM "anon";

CREATE TABLE "public"."venues" (
  "venue_id"                   uuid                     NOT NULL DEFAULT gen_random_uuid(),
  "venue_name"                 text                     NOT NULL,
  "capacity"                   integer                  NOT NULL,
  "postal_code"                text                     NOT NULL,
  "block_number"               text                     NOT NULL,
  "street_name"                text                     NOT NULL,
  "building_name"              text,
  "unit_number"                text,
  "wheelchair_accessible"      boolean                  NOT NULL,
  "blind_accessible"           boolean                  NOT NULL,
  "accessibility_notes"        text,
  "facilities"                 text[]                   NOT NULL,
  "supported_room_layouts"     text[]                   NOT NULL,
  "operating_hours"            jsonb                    NOT NULL,
  "default_setup_minutes"      integer                  NOT NULL,
  "default_turnaround_minutes" integer                  NOT NULL,
  "version"                    integer                  NOT NULL DEFAULT 1,
  "updated_at"                 timestamp with time zone NOT NULL DEFAULT clock_timestamp(),
  "deleted_at"                 timestamp with time zone,
  "emergency_access"           text,
  "safety_restrictions"        text,
  CONSTRAINT "venue_setup_within_a_day" CHECK ((default_setup_minutes <= 1440)),
  CONSTRAINT "venue_turnaround_within_a_day" CHECK ((default_turnaround_minutes <= 1440)),
  CONSTRAINT "venues_block_number_check" CHECK ((btrim(block_number) <> ''::text)),
  CONSTRAINT "venues_capacity_check" CHECK ((capacity > 0)),
  CONSTRAINT "venues_default_setup_minutes_check" CHECK ((default_setup_minutes >= 0)),
  CONSTRAINT "venues_default_turnaround_minutes_check" CHECK ((default_turnaround_minutes >= 0)),
  CONSTRAINT "venues_operating_hours_check1"
    CHECK ((operating_hours ?& ARRAY['monday'::text, 'tuesday'::text, 'wednesday'::text, 'thursday'::text, 'friday'::text, 'saturday'::text, 'sunday'::text])),
  CONSTRAINT "venues_operating_hours_check" CHECK ((jsonb_typeof(operating_hours) = 'object'::text)),
  CONSTRAINT "venues_pkey" PRIMARY KEY (venue_id),
  CONSTRAINT "venues_postal_code_check" CHECK ((postal_code ~ '^[0-9]{6}$'::text)),
  CONSTRAINT "venues_street_name_check" CHECK ((btrim(street_name) <> ''::text)),
  CONSTRAINT "venues_venue_name_check" CHECK ((btrim(venue_name) <> ''::text)),
  CONSTRAINT "venues_version_check" CHECK ((version >= 1))
);

REVOKE ALL ON TABLE "public"."venues" FROM "anon";

ALTER SEQUENCE "public"."equipment_equipment_id_seq" OWNED BY "public"."equipment"."equipment_id";

ALTER SEQUENCE "public"."equipment_request_equipment_request_id_seq" OWNED BY "public"."equipment_request"."equipment_request_id";

ALTER SEQUENCE "public"."roles_role_id_seq" OWNED BY "public"."roles"."role_id";

CREATE TYPE "public"."event_change_request_status" AS ENUM (
  'pending_review',
  'approved',
  'rejected'
);

ALTER TABLE "public"."event_change_request"
  ADD COLUMN "status" public.event_change_request_status NOT NULL DEFAULT 'pending_review'::public.event_change_request_status;

ALTER TABLE "public"."event_change_request"
  ADD COLUMN "expected_event_updated_at" timestamp WITH time zone NOT NULL;

ALTER TABLE "public"."event_change_request"
  ADD COLUMN "submitted_at" timestamp WITH time zone NOT NULL DEFAULT clock_timestamp();

ALTER TABLE "public"."event_change_request"
  ADD COLUMN "reviewed_at" timestamp WITH time zone;

ALTER TABLE "public"."event_change_request"
  ADD COLUMN "reviewed_by" uuid;

ALTER TABLE "public"."event_change_request"
  ADD COLUMN "importance" text NOT NULL DEFAULT 'important'::text;

ALTER TABLE "public"."event_change_request"
  ADD COLUMN "decision_reason" text;

CREATE TYPE "public"."event_status" AS ENUM (
  'draft',
  'submitted',
  'planning',
  'rejected',
  'pending_safety_checks',
  'confirmed',
  'completed',
  'cancelled'
);

CREATE TYPE "public"."facility" AS ENUM (
  'projector',
  'whiteboard',
  'sound_system',
  'microphone',
  'wifi',
  'stage',
  'catering_area',
  'video_conferencing',
  'parking',
  'air_conditioning'
);

CREATE TYPE "public"."review_outcome" AS ENUM (
  'approved',
  'rejected',
  'clarification_requested'
);

ALTER TABLE "public"."event_request_review"
  ADD COLUMN "outcome" public.review_outcome NOT NULL;

ALTER TABLE "public"."event_request_review"
  ADD COLUMN "comments" text;

ALTER TABLE "public"."event_request_review"
  ADD COLUMN "created_at" timestamp WITH time zone NOT NULL DEFAULT now();

CREATE TYPE "public"."room_layout" AS ENUM (
  'theatre',
  'classroom',
  'boardroom',
  'u_shape',
  'banquet',
  'standing',
  'exhibition',
  'cabaret'
);

ALTER TABLE "public"."event_request"
  ADD COLUMN "room_layout" public.room_layout;

ALTER TABLE "public"."event_request"
  ADD COLUMN "required_facilities" public.facility[] DEFAULT '{}'::public.facility[];

ALTER TABLE "public"."event_request"
  ADD COLUMN "need_wheelchair_accessibility" boolean NOT NULL DEFAULT false;

ALTER TABLE "public"."event_request"
  ADD COLUMN "need_blind_accessibility" boolean NOT NULL DEFAULT false;

ALTER TABLE "public"."event_request"
  ADD COLUMN "status" public.event_status NOT NULL DEFAULT 'draft'::public.event_status;

ALTER TABLE "public"."event_request"
  ADD COLUMN "submitted_at" timestamp WITH time zone;

ALTER TABLE "public"."event_request"
  ADD COLUMN "created_at" timestamp WITH time zone NOT NULL DEFAULT now();

ALTER TABLE "public"."event_request"
  ADD COLUMN "updated_at" timestamp WITH time zone NOT NULL DEFAULT now();

ALTER TABLE "public"."event_request"
  ADD COLUMN "equipment_requirements" jsonb;

ALTER TABLE "public"."event_request"
  ADD COLUMN "registration_needs" text;

ALTER TABLE "public"."events"
  ADD COLUMN "room_layout" public.room_layout NOT NULL;

ALTER TABLE "public"."events"
  ADD COLUMN "required_facilities" public.facility[] NOT NULL DEFAULT '{}'::public.facility[];

ALTER TABLE "public"."events"
  ADD COLUMN "need_wheelchair_accessibility" boolean NOT NULL DEFAULT false;

ALTER TABLE "public"."events"
  ADD COLUMN "need_blind_accessibility" boolean NOT NULL DEFAULT false;

ALTER TABLE "public"."events"
  ADD COLUMN "equipment_requirements" jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE "public"."events"
  ADD COLUMN "registration_needs" text;

ALTER TABLE "public"."events"
  ADD COLUMN "status" public.event_status NOT NULL DEFAULT 'planning'::public.event_status;

ALTER TABLE "public"."events"
  ADD COLUMN "event_organiser_id" uuid NOT NULL;

ALTER TABLE "public"."events"
  ADD COLUMN "event_coordinator_id" uuid;

ALTER TABLE "public"."events"
  ADD COLUMN "technical_support_id" uuid;

ALTER TABLE "public"."events"
  ADD COLUMN "venue_staff_id" uuid;

ALTER TABLE "public"."events"
  ADD COLUMN "created_at" timestamp WITH time zone NOT NULL DEFAULT now();

ALTER TABLE "public"."events"
  ADD COLUMN "updated_at" timestamp WITH time zone NOT NULL DEFAULT now();

ALTER TABLE "public"."events"
  ADD COLUMN "venue_id" uuid;

ALTER TABLE "public"."events"
  ADD COLUMN "registration_ready" boolean NOT NULL DEFAULT false;

ALTER TABLE "public"."events"
  ADD COLUMN "crowd_movement_plan" text;

ALTER TABLE "public"."events"
  ADD COLUMN "equipment_placement_plan" text;

ALTER TABLE "public"."events"
  ADD COLUMN "safety_rework_required" boolean NOT NULL DEFAULT false;

ALTER TABLE "public"."events"
  ADD COLUMN "safety_rework_requested_at" timestamp WITH time zone;

ALTER TABLE "public"."events"
  ADD COLUMN "safety_rework_arrangements" text[] NOT NULL DEFAULT ARRAY[]::text[];

ALTER TABLE "public"."events"
  ADD COLUMN "safety_approved_at" timestamp WITH time zone;

ALTER TABLE "public"."events"
  ADD COLUMN "safety_officer_id" uuid;

ALTER TABLE "public"."events"
  ADD COLUMN "registration_opens_at" timestamp WITH time zone;

ALTER TABLE "public"."events"
  ADD COLUMN "registration_closes_at" timestamp WITH time zone;

ALTER TABLE "public"."events"
  ADD COLUMN "waiting_list_enabled" boolean NOT NULL DEFAULT false;

CREATE OR REPLACE FUNCTION public.assign_event_coordinator()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  AS $function$
declare
  chosen_coordinator uuid;
begin
  if new.event_coordinator_id is null then
    select u.user_id into chosen_coordinator
    from users u
    join user_roles ur on ur.user_id = u.user_id
    join roles r on r.role_id = ur.role_id
    where r.role_name = 'Event Coordinator'
    order by random()
    limit 1;

    new.event_coordinator_id := chosen_coordinator;
  end if;

  return new;
end;
$function$;

CREATE OR REPLACE FUNCTION public.assign_event_request_coordinator (
  p_event_request_id bigint,
  p_coordinator_id   uuid
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    assigned_request public.event_request;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_coordinator_lead') then
        return jsonb_build_object(
            'error', 'Only Event Coordinator Leads can assign event coordinators.',
            'status', 403
        );
    end if;
    if p_coordinator_id is null or not exists (
        select 1
        from public.user_roles ur
        join public.roles ro on ro.role_id = ur.role_id
        where ur.user_id = p_coordinator_id
          and replace(lower(trim(ro.role_name)), ' ', '_') = 'event_coordinator'
    ) then
        return jsonb_build_object(
            'error', 'Choose a user with the Event Coordinator role.',
            'status', 400
        );
    end if;

    select * into assigned_request
    from public.event_request
    where event_request_id = p_event_request_id
    for update;

    if not found then
        return jsonb_build_object('error', 'Event request not found.', 'status', 404);
    end if;
    if assigned_request.status <> 'submitted'::public.event_status
       or assigned_request.event_coordinator_id is not null then
        return jsonb_build_object(
            'error', 'This request is no longer available for assignment. Refresh the queue.',
            'status', 409
        );
    end if;

    update public.event_request
    set event_coordinator_id = p_coordinator_id,
        updated_at = now()
    where event_request_id = p_event_request_id
    returning * into assigned_request;

    update public.events
    set event_coordinator_id = p_coordinator_id
    where event_request_id = p_event_request_id;


    return jsonb_build_object(
        'message', 'Event Coordinator assigned successfully.',
        'event_request', to_jsonb(assigned_request)
    );
end;
$function$;

REVOKE ALL ON FUNCTION "public"."assign_event_request_coordinator"(bigint, uuid) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.attendee_registration_events()
  RETURNS jsonb
  LANGUAGE plpgsql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('attendee') then
        return jsonb_build_object('error', 'Only attendees can browse registration events.', 'status', 403);
    end if;
    return (
        select jsonb_build_object('events', coalesce(jsonb_agg(jsonb_build_object(
            'event_id', e.event_id, 'event_name', e.event_name, 'description', e.description,
            'start_datetime', e.start_datetime, 'end_datetime', e.end_datetime,
            'status', e.status, 'registration_opens_at', e.registration_opens_at,
            'registration_closes_at', e.registration_closes_at,
            'waiting_list_enabled', e.waiting_list_enabled, 'capacity', e.capacity_needed,
            'available_capacity', greatest(0, e.capacity_needed - (select count(*) from public.event_registration r
                where r.event_id = e.event_id and r.status = 'registered')),
            'registration_status', case
                when e.status <> 'confirmed' or e.end_datetime <= now() then 'unavailable'
                when now() < e.registration_opens_at then 'not_open'
                when now() >= e.registration_closes_at then 'closed'
                else 'open' end,
            'my_registration', (select r.status from public.event_registration r
                where r.event_id = e.event_id and r.attendee_id = auth.uid())
        ) order by e.start_datetime), '[]'::jsonb))
        from public.events e where auth.uid() is not null
            and e.registration_opens_at is not null
            and e.status in ('confirmed', 'completed', 'cancelled'));
    end;
$function$;

REVOKE ALL ON FUNCTION "public"."attendee_registration_events"() FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.auto_assign_event_staff()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
begin
    if new.event_request_id is null then
        return new;
    end if;
    new.venue_staff_id := coalesce(
        new.venue_staff_id,
        public.random_user_with_role(array['venue_staff']));
    new.technical_support_id := coalesce(
        new.technical_support_id,
        public.random_user_with_role(array['technical_support_staff', 'technical_support']));
    new.safety_officer_id := coalesce(
        new.safety_officer_id,
        public.random_user_with_role(array['safety_officer']));
    return new;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."auto_assign_event_staff"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.block_venue (
  p_venue_id uuid,
  p_starts   timestamp with time zone,
  p_ends     timestamp with time zone,
  p_reason   text
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    block public.venue_blocks;
    venue text;
    reason text := trim(coalesce(p_reason, ''));
    affected jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('venue_staff') then
        return jsonb_build_object('error', 'Only Venue Staff can mark a venue unavailable.', 'status', 403);
    end if;
    select venue_name into venue from public.venues where venue_id = p_venue_id and deleted_at is null;
    if not found then
        return jsonb_build_object('error', 'Venue not found or access unavailable.', 'status', 404);
    end if;
    if p_starts is null or p_ends is null or p_ends <= p_starts then
        return jsonb_build_object('error', 'The end must be after the start.', 'status', 400);
    end if;
    if reason = '' or length(reason) > 500 then
        return jsonb_build_object('error', 'Enter a reason (maximum 500 characters).', 'status', 400);
    end if;

    insert into public.venue_blocks (venue_id, starts_at, ends_at, reason, created_by)
    values (p_venue_id, p_starts, p_ends, reason, auth.uid()) returning * into block;

    with cancelled as (
        update public.venue_booking_requests b
        set status = 'cancelled', cancelled_at = now(), cancellation_reason = 'Venue unavailable: ' || reason
        where b.venue_id = p_venue_id and b.status in ('submitted', 'approved')
          and tstzrange(b.occupied_from, b.occupied_until, '[)') && tstzrange(p_starts, p_ends, '[)')
        returning b.*
    )
    select coalesce(jsonb_agg(jsonb_build_object(
        'booking_id', c.booking_id, 'event_id', c.event_id, 'event_name', c.event_name,
        'starts_at', c.starts_at, 'ends_at', c.ends_at) order by c.starts_at), '[]'::jsonb)
    into affected from cancelled c;

    return jsonb_build_object('block', to_jsonb(block), 'affected', affected);
end;
$function$;

REVOKE ALL ON FUNCTION "public"."block_venue"(uuid, timestamp WITH time zone, timestamp WITH time zone, text) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.can_reserve_equipment()
  RETURNS boolean
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    select auth.uid() is not null and exists (
        select 1 from public.user_roles ur join public.roles r using (role_id)
        where ur.user_id = auth.uid()
          and lower(replace(btrim(r.role_name), ' ', '_'))
              in ('technical_support_staff', 'technical_support')
    );
$function$;

REVOKE ALL ON FUNCTION "public"."can_reserve_equipment"() FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.cancel_equipment_reservation (
  p_reservation_id uuid
)
  RETURNS jsonb
  LANGUAGE sql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    select public.change_equipment_reservation(p_reservation_id, null, true);
$function$;

REVOKE ALL ON FUNCTION "public"."cancel_equipment_reservation"(uuid) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.cancel_event_request (
  p_request_id integer
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare saved public.event_request;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    select * into saved from public.event_request where event_request_id = p_request_id for update;
    if not found or (auth.uid() is distinct from saved.event_organiser_id and auth.uid() is distinct from saved.event_coordinator_id) then
        return jsonb_build_object('error', 'Event request not found or access unavailable.', 'status', 404);
    end if;
    if saved.status not in ('draft', 'submitted', 'rejected') then
        return jsonb_build_object('error', 'Cancel the operational event after approval.', 'status', 409);
    end if;
    update public.event_request set status = 'cancelled', updated_at = clock_timestamp()
    where event_request_id = p_request_id returning * into saved;
    return jsonb_build_object('event_request', to_jsonb(saved));
end;
$function$;

REVOKE ALL ON FUNCTION "public"."cancel_event_request"(integer) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.cancel_planned_event (
  p_event_id integer
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare saved public.events;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    select * into saved from public.events where event_id = p_event_id for update;
    if not found or (auth.uid() is distinct from saved.event_organiser_id and auth.uid() is distinct from saved.event_coordinator_id) then
        return jsonb_build_object('error', 'Event not found or access unavailable.', 'status', 404);
    end if;
    if saved.status not in ('planning', 'pending_safety_checks', 'confirmed') then
        return jsonb_build_object('error', 'Only Planning, Pending Safety Checks, or Confirmed events can be cancelled.', 'status', 409);
    end if;
    update public.events set status = 'cancelled' where event_id = p_event_id returning * into saved;
    return jsonb_build_object('event', to_jsonb(saved));
end;
$function$;

REVOKE ALL ON FUNCTION "public"."cancel_planned_event"(integer) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.cancel_venue_booking (
  p_booking_id uuid
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare booking public.venue_booking_requests;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    select * into booking from public.venue_booking_requests
    where booking_id = p_booking_id and requested_by = auth.uid() for update;
    if not found then
        return jsonb_build_object('error', 'Booking request not found or access unavailable.', 'status', 404);
    end if;
    if booking.status not in ('submitted', 'approved') then
        return jsonb_build_object('error', 'Only pending or approved bookings can be cancelled.', 'status', 409);
    end if;
    if not exists (select 1 from public.events where event_id = booking.event_id
                   and status in ('planning', 'pending_safety_checks') and start_datetime > now()) then
        return jsonb_build_object('error', 'Bookings can only be cancelled before the event is confirmed and has started.', 'status', 409);
    end if;
    update public.venue_booking_requests set status = 'cancelled', cancelled_at = now()
    where booking_id = p_booking_id returning * into booking;
    return jsonb_build_object('booking', to_jsonb(booking));
end;
$function$;

REVOKE ALL ON FUNCTION "public"."cancel_venue_booking"(uuid) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.change_equipment_reservation (
  p_reservation_id uuid,
  p_quantity       integer,
  p_cancel         boolean
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    saved public.equipment_reservations;
    linked public.equipment_request;
    stock integer;
    maximum bigint;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if p_cancel is null or (not p_cancel and (p_quantity is null or p_quantity <= 0)) then
        return jsonb_build_object('error', 'Quantity must be a positive whole number.', 'status', 400);
    end if;
    select * into saved from public.equipment_reservations
    where reservation_id = p_reservation_id and created_by = auth.uid();
    if not found then
        return jsonb_build_object('error', 'Reservation not found or access unavailable.', 'status', 404);
    end if;
    -- Match review/reserve lock order: event -> stock -> request -> reservation.
    perform 1 from public.events where event_id::text = saved.event_id::text for update;
    select total_quantity into stock from public.equipment
    where equipment_id = saved.equipment_id for update;
    if saved.equipment_request_id is not null then
        select * into linked from public.equipment_request
        where equipment_request_id = saved.equipment_request_id for update;
        if not found then
            return jsonb_build_object('error', 'Linked equipment request not found.', 'status', 409);
        end if;
    end if;
    select * into saved from public.equipment_reservations
    where reservation_id = p_reservation_id and created_by = auth.uid() for update;
    if not found then
        return jsonb_build_object('error', 'Reservation not found or access unavailable.', 'status', 404);
    end if;
    if p_cancel then
        if saved.equipment_request_id is not null then
            update public.equipment_request set status = case when linked.status = 'pending' then 'pending' else 'cancelled' end, accepted_quantity = 0
            where equipment_request_id = saved.equipment_request_id returning * into linked;
        end if;
        -- The cancelled request must not re-enter the legacy stock calculation.
        delete from public.equipment_reservations where reservation_id = p_reservation_id;
        return jsonb_build_object('cancelled', true, 'reservation_id', p_reservation_id,
            'equipment_request', case when saved.equipment_request_id is not null then to_jsonb(linked) else null end);
    end if;
    maximum := greatest(0, stock - public.equipment_peak(saved.equipment_id, saved.starts_at, saved.ends_at) + saved.quantity);
    if p_quantity > saved.quantity and p_quantity > maximum then
        return jsonb_build_object('error', format('Insufficient equipment: you can reserve at most %s for this event.', maximum),
            'maximum_quantity', maximum, 'status', 409);
    end if;
    update public.equipment_reservations set quantity = p_quantity
    where reservation_id = p_reservation_id returning * into saved;
    if saved.equipment_request_id is not null and linked.status <> 'pending' then
        update public.equipment_request set accepted_quantity = p_quantity,
            status = case when p_quantity < quantity then 'partially_accepted' else 'accepted' end
        where equipment_request_id = saved.equipment_request_id returning * into linked;
    end if;
    return jsonb_build_object('reservation', to_jsonb(saved),
        'equipment_request', case when saved.equipment_request_id is not null then to_jsonb(linked) else null end);
end;
$function$;

REVOKE ALL ON FUNCTION "public"."change_equipment_reservation"(uuid, integer, boolean) FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.create_event_from_approved_request()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
begin
    insert into public.events (
        event_request_id,
        event_name,
        purpose,
        description,
        start_datetime,
        end_datetime,
        capacity_needed,
        room_layout,
        required_facilities,
        need_wheelchair_accessibility,
        need_blind_accessibility,
        equipment_requirements,
        registration_needs,
        status,
        event_organiser_id,
        event_coordinator_id
    )
    values (
        new.event_request_id,
        new.event_name,
        new.purpose,
        new.description,
        new.start_datetime,
        new.end_datetime,
        new.capacity_needed,
        new.room_layout,
        coalesce(
            new.required_facilities,
            '{}'::public.facility[]
        ),
        new.need_wheelchair_accessibility,
        new.need_blind_accessibility,
        coalesce(
            new.equipment_requirements,
            '[]'::jsonb
        ),
        new.registration_needs,
        'planning',
        new.event_organiser_id,
        new.event_coordinator_id
    )
    on conflict (event_request_id) do nothing;

    return new;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."create_event_from_approved_request"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.eligible_event_change_request_events()
  RETURNS jsonb
  LANGUAGE plpgsql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare result jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_organiser') then
        return jsonb_build_object('error', 'Only Event Organisers can submit event change requests.', 'status', 403);
    end if;
    select coalesce(jsonb_agg(to_jsonb(e) order by e.start_datetime), '[]'::jsonb)
      into result from public.events e
     where e.event_organiser_id = auth.uid()
       and e.status in ('planning', 'pending_safety_checks', 'confirmed')
       and not exists (
           select 1 from public.event_change_request c
            where c.event_id = e.event_id and c.status = 'pending_review'
       );
    return jsonb_build_object('events', result);
end;
$function$;

REVOKE ALL ON FUNCTION "public"."eligible_event_change_request_events"() FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.equipment_availability (
  p_event_id text
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare ev jsonb; s timestamptz; f timestamptz; items jsonb;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.'); end if;
    select to_jsonb(e) into ev from public.events e where e.event_id::text = p_event_id;
    if ev is null then return jsonb_build_object('error', 'Event not found.'); end if;
    s := coalesce(ev->>'start_datetime', ev->>'starts_at')::timestamptz;
    f := coalesce(ev->>'end_datetime', ev->>'ends_at')::timestamptz;
    if s is null or f is null or f <= s then
        return jsonb_build_object('error', 'Set a valid event start and end time before reserving equipment.');
    end if;
    select coalesce(jsonb_agg(jsonb_build_object(
        'equipment_id', q.equipment_id, 'name', concat_ws(' - ', q.equipment_type, q.equipment_model),
        'total_quantity', q.total_quantity,
        'available_quantity', greatest(0, q.total_quantity - public.equipment_peak(q.equipment_id, s, f)),
        'reserved_quantity', coalesce(r.quantity, 0), 'standalone_reserved', coalesce(r.standalone, false)
    ) order by q.equipment_type, q.equipment_model), '[]'::jsonb) into items
    from public.equipment q left join (
        select equipment_id, sum(quantity) as quantity, bool_or(equipment_request_id is null) as standalone
        from public.equipment_reservations where event_id::text = p_event_id group by equipment_id
    ) r on r.equipment_id = q.equipment_id;
    return jsonb_build_object('equipment', items, 'starts_at', s, 'ends_at', f);
end;
$function$;

REVOKE ALL ON FUNCTION "public"."equipment_availability"(text) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.equipment_events()
  RETURNS jsonb
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    select coalesce(jsonb_agg(jsonb_build_object(
        'event_id', e.event_id::text, 'event_name', e.event_name,
        'starts_at', coalesce(to_jsonb(e)->>'start_datetime', to_jsonb(e)->>'starts_at'),
        'ends_at', coalesce(to_jsonb(e)->>'end_datetime', to_jsonb(e)->>'ends_at')
    ) order by e.event_name), '[]'::jsonb) from public.events e;
$function$;

REVOKE ALL ON FUNCTION "public"."equipment_events"() FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.equipment_peak (
  p_equipment_id integer,
  p_start        timestamp with time zone,
  p_end          timestamp with time zone
)
  RETURNS bigint
  LANGUAGE sql
  STABLE
  SET search_path TO 'public'
  AS $function$
    with commitments as (
        select equipment_id, quantity, starts_at, ends_at from public.equipment_reservations
        union all
        select r.equipment_id, coalesce(r.accepted_quantity, r.quantity),
            coalesce(to_jsonb(e)->>'start_datetime', to_jsonb(e)->>'starts_at')::timestamptz,
            coalesce(to_jsonb(e)->>'end_datetime', to_jsonb(e)->>'ends_at')::timestamptz
        from public.equipment_request r join public.events e on e.event_id = r.event_id
        where r.status in ('accepted', 'in_progress', 'partially_accepted', 'completed')
          and not exists (select 1 from public.equipment_reservations booked
              where booked.equipment_request_id = r.equipment_request_id)
    ), changes as (
        select greatest(starts_at, p_start) as moment, quantity::bigint as delta
        from commitments
        where equipment_id = p_equipment_id and starts_at < p_end and ends_at > p_start
        union all
        select least(ends_at, p_end), -quantity::bigint
        from commitments
        where equipment_id = p_equipment_id and starts_at < p_end and ends_at > p_start
    ), usage as (
        select sum(sum(delta)) over (order by moment) as used from changes group by moment
    ) select coalesce(max(used), 0)::bigint from usage;
$function$;

REVOKE ALL ON FUNCTION "public"."equipment_peak"(integer, timestamp WITH time zone, timestamp WITH time zone) FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.equipment_request_review_queue()
  RETURNS jsonb
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    select coalesce(jsonb_agg(to_jsonb(r) || jsonb_build_object(
        'event_name', e.event_name, 'linked_reservation',
        (select to_jsonb(b) from public.equipment_reservations b where b.equipment_request_id = r.equipment_request_id))
        order by r.requested_at), '[]'::jsonb)
    from public.equipment_request r join public.events e on e.event_id::text = r.event_id::text
    where public.can_reserve_equipment() and e.technical_support_id = auth.uid();
$function$;

REVOKE ALL ON FUNCTION "public"."equipment_request_review_queue"() FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.equipment_window_availability (
  p_start timestamp with time zone,
  p_end   timestamp with time zone
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
begin
    if auth.uid() is null then raise exception 'Authentication required'; end if;
    if p_start is null or p_end is null or p_end <= p_start then
        raise exception 'A valid time window is required';
    end if;
    return (select coalesce(jsonb_agg(jsonb_build_object(
        'equipment_id', q.equipment_id, 'equipment_type', q.equipment_type,
        'equipment_model', q.equipment_model, 'total_quantity', q.total_quantity,
        'available_quantity', greatest(0, q.total_quantity - public.equipment_peak(q.equipment_id, p_start, p_end))
    ) order by q.equipment_type, q.equipment_model), '[]'::jsonb) from public.equipment q);
end;
$function$;

REVOKE ALL ON FUNCTION "public"."equipment_window_availability"(timestamp WITH time zone, timestamp WITH time zone) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.event_change_request_for_review (
  p_request_id bigint
)
  RETURNS jsonb
  LANGUAGE plpgsql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare result jsonb;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_booking_role('event_coordinator') then return jsonb_build_object('error', 'Only Event Coordinators can review event change requests.', 'status', 403); end if;
    select to_jsonb(c) || jsonb_build_object('event_name', e.event_name) into result
    from public.event_change_request c join public.events e on e.event_id = c.event_id
    where c.event_change_request_id = p_request_id and e.event_coordinator_id = auth.uid();
    if result is null then return jsonb_build_object('error', 'Change request not found or access unavailable.', 'status', 404); end if;
    return jsonb_build_object('change_request', result, 'preparation_impacts', public.event_change_request_impacts(result->'changes'));
end;
$function$;

REVOKE ALL ON FUNCTION "public"."event_change_request_for_review"(bigint) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.event_change_request_impacts (
  p_changes jsonb
)
  RETURNS jsonb
  LANGUAGE plpgsql
  IMMUTABLE
  SET search_path TO 'public'
  AS $function$
declare impacts text[] := array[]::text[];
begin
    if p_changes ?| array['start_datetime', 'end_datetime'] then
        impacts := impacts || array['venue_availability', 'equipment_reservations', 'event_schedule'];
    end if;
    if p_changes ? 'capacity_needed' then
        impacts := impacts || array['venue_capacity', 'venue_suitability'];
    end if;
    if p_changes ?| array['room_layout', 'required_facilities'] then
        if not ('venue_suitability' = any(impacts)) then impacts := array_append(impacts, 'venue_suitability'); end if;
    end if;
    if p_changes ?| array['need_wheelchair_accessibility', 'need_blind_accessibility'] then
        impacts := array_append(impacts, 'accessibility_arrangements');
        if not ('venue_suitability' = any(impacts)) then impacts := array_append(impacts, 'venue_suitability'); end if;
    end if;
    if p_changes ? 'equipment_requirements' then
        impacts := array_append(impacts, 'equipment_availability');
        if not ('equipment_reservations' = any(impacts)) then impacts := array_append(impacts, 'equipment_reservations'); end if;
    end if;
    return to_jsonb(impacts);
end;
$function$;

REVOKE ALL ON FUNCTION "public"."event_change_request_impacts"(jsonb) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.event_change_requests_for_coordinator (
  p_status text DEFAULT NULL::text
)
  RETURNS jsonb
  LANGUAGE plpgsql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare result jsonb;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_booking_role('event_coordinator') then return jsonb_build_object('error', 'Only Event Coordinators can review event change requests.', 'status', 403); end if;
    if p_status is not null and p_status not in ('pending_review', 'approved', 'rejected') then return jsonb_build_object('error', 'Choose a valid change request status.', 'status', 400); end if;
    select coalesce(jsonb_agg(
        to_jsonb(c) || jsonb_build_object(
            'event_name', e.event_name,
            'changed_fields', (select coalesce(jsonb_agg(key order by key), '[]'::jsonb) from jsonb_object_keys(c.changes) key),
            'preparation_impacts', public.event_change_request_impacts(c.changes)
        ) order by (c.status = 'pending_review') desc, c.submitted_at desc
    ), '[]'::jsonb) into result
    from public.event_change_request c join public.events e on e.event_id = c.event_id
    where e.event_coordinator_id = auth.uid() and (p_status is null or c.status::text = p_status);
    return jsonb_build_object('change_requests', result);
end;
$function$;

REVOKE ALL ON FUNCTION "public"."event_change_requests_for_coordinator"(text) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.event_change_requests_for_event (
  p_event_id integer
)
  RETURNS jsonb
  LANGUAGE plpgsql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare planned public.events; result jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    select * into planned from public.events where event_id = p_event_id;
    if not found or (auth.uid() is distinct from planned.event_organiser_id
                 and auth.uid() is distinct from planned.event_coordinator_id) then
        return jsonb_build_object('error', 'Event not found or access unavailable.', 'status', 404);
    end if;
    select coalesce(jsonb_agg(to_jsonb(c) order by c.submitted_at desc), '[]'::jsonb)
      into result from public.event_change_request c where c.event_id = p_event_id;
    return jsonb_build_object('change_requests', result);
end;
$function$;

REVOKE ALL ON FUNCTION "public"."event_change_requests_for_event"(integer) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.event_change_requests_for_organiser()
  RETURNS jsonb
  LANGUAGE plpgsql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare result jsonb;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_booking_role('event_organiser') then return jsonb_build_object('error', 'Only Event Organisers can view their event change requests.', 'status', 403); end if;
    select coalesce(jsonb_agg(
        to_jsonb(c) || jsonb_build_object(
            'event_name', e.event_name,
            'changed_fields', (select coalesce(jsonb_agg(key order by key), '[]'::jsonb) from jsonb_object_keys(c.changes) key)
        ) order by c.submitted_at desc
    ), '[]'::jsonb) into result
    from public.event_change_request c
    join public.events e on e.event_id = c.event_id
    where c.requested_by = auth.uid();
    return jsonb_build_object('change_requests', result);
end;
$function$;

REVOKE ALL ON FUNCTION "public"."event_change_requests_for_organiser"() FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.event_confirmation_blockers (
  p_event public.events
)
  RETURNS text[]
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare blockers text[] := '{}'; item jsonb; reserved bigint;
begin
    if p_event.event_coordinator_id is null then
        blockers := array_append(blockers, 'An Event Coordinator must be assigned.');
    end if;
    if p_event.start_datetime is null or p_event.end_datetime is null
        or p_event.end_datetime <= p_event.start_datetime then
        blockers := array_append(blockers, 'Valid event dates are required.');
    end if;
    if not exists (
        select 1 from public.venue_booking_requests b join public.venues v using (venue_id)
        where b.event_id = p_event.event_id and b.status = 'approved'
          and b.starts_at = p_event.start_datetime and b.ends_at = p_event.end_datetime
          and (p_event.capacity_needed is null or b.attendance = p_event.capacity_needed)
          and v.deleted_at is null
          and cardinality(public.venue_shortfalls_for_event(v, p_event)) = 0
    ) then
        blockers := array_append(blockers, 'An approved venue booking matching the event is required.');
    end if;
    if p_event.equipment_requirements is null then
        blockers := array_append(blockers, 'Record equipment requirements, or an empty list if none are needed.');
    elsif jsonb_typeof(p_event.equipment_requirements) <> 'array' then
        blockers := array_append(blockers, 'Equipment requirements must be a list of types and quantities.');
    else
        for item in select value from jsonb_array_elements(p_event.equipment_requirements) loop
            if jsonb_typeof(item) <> 'object'
                or jsonb_typeof(item->'equipment_type') is distinct from 'string'
                or jsonb_typeof(item->'quantity') is distinct from 'number'
                or nullif(btrim(item->>'equipment_type'), '') is null
                or coalesce(item->>'quantity', '') !~ '^[1-9][0-9]*$' then
                blockers := array_append(blockers, 'Each equipment requirement needs a type and positive quantity.');
                continue;
            end if;
            select coalesce(sum(r.quantity), 0) into reserved
            from public.equipment_reservations r join public.equipment q using (equipment_id)
            where r.event_id = p_event.event_id
              and lower(btrim(q.equipment_type)) = lower(btrim(item->>'equipment_type'))
              and r.starts_at <= p_event.start_datetime and r.ends_at >= p_event.end_datetime;
            if reserved < (item->>'quantity')::numeric then
                blockers := array_append(blockers, 'Reserve all required ' || (item->>'equipment_type') || '.');
            end if;
        end loop;
    end if;
    if exists (
        select 1 from public.equipment_request q where q.event_id = p_event.event_id
        and not exists (select 1 from public.equipment_reservations r
            where r.equipment_request_id = q.equipment_request_id
              and r.quantity >= q.quantity
              and r.starts_at <= p_event.start_datetime and r.ends_at >= p_event.end_datetime)
    ) then
        blockers := array_append(blockers, 'Every equipment request must be fully reserved.');
    end if;
    if nullif(btrim(p_event.registration_needs), '') is not null and not p_event.registration_ready then
        blockers := array_append(blockers, 'The Event Coordinator must confirm registration readiness.');
    end if;
    return blockers;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."event_confirmation_blockers"(public.events) FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.event_coordinator_lead_dashboard()
  RETURNS jsonb
  LANGUAGE plpgsql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    dashboard_items jsonb;
    available_coordinators jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_coordinator_lead') then
        return jsonb_build_object(
            'error', 'Only Event Coordinator Leads can view this dashboard.',
            'status', 403
        );
    end if;

    select coalesce(jsonb_agg(
        dashboard.item
        order by dashboard.item->>'start_datetime' nulls last,
                 dashboard.item->>'event_name'
    ), '[]'::jsonb)
    into dashboard_items
    from (
        select jsonb_build_object(
            'item_type', 'request',
            'event_id', null,
            'event_request_id', r.event_request_id,
            'event_name', r.event_name,
            'purpose', r.purpose,
            'description', r.description,
            'start_datetime', r.start_datetime,
            'end_datetime', r.end_datetime,
            'capacity_needed', r.capacity_needed,
            'status', r.status::text,
            'event_coordinator_id', r.event_coordinator_id,
            'event_coordinator_name', coalesce(
                nullif(btrim(coordinator.name), ''),
                nullif(btrim(coordinator.email), '')
            ),
            'event_organiser_name', coalesce(
                nullif(btrim(organiser.name), ''),
                nullif(btrim(organiser.email), '')
            )
        ) as item
        from public.event_request r
        left join public.users coordinator
            on coordinator.user_id = r.event_coordinator_id
        left join public.users organiser
            on organiser.user_id = r.event_organiser_id
        where r.status = 'submitted'::public.event_status

        union all

        select jsonb_build_object(
            'item_type', 'event',
            'event_id', e.event_id,
            'event_request_id', e.event_request_id,
            'event_name', e.event_name,
            'purpose', e.purpose,
            'description', e.description,
            'start_datetime', e.start_datetime,
            'end_datetime', e.end_datetime,
            'capacity_needed', e.capacity_needed,
            'status', e.status::text,
            'event_coordinator_id', e.event_coordinator_id,
            'event_coordinator_name', coalesce(
                nullif(btrim(coordinator.name), ''),
                nullif(btrim(coordinator.email), '')
            ),
            'event_organiser_name', coalesce(
                nullif(btrim(organiser.name), ''),
                nullif(btrim(organiser.email), '')
            )
        ) as item
        from public.events e
        left join public.users coordinator
            on coordinator.user_id = e.event_coordinator_id
        left join public.users organiser
            on organiser.user_id = e.event_organiser_id
        where e.status::text in (
            'planning',
            'pending_safety_checks',
            'confirmed'
        )
    ) dashboard;

    select coalesce(jsonb_agg(
        jsonb_build_object(
            'id', eligible.user_id,
            'name', coalesce(
                nullif(btrim(u.name), ''),
                nullif(btrim(u.email), ''),
                u.user_id::text
            )
        ) order by coalesce(
            nullif(btrim(u.name), ''),
            nullif(btrim(u.email), ''),
            u.user_id::text
        )
    ), '[]'::jsonb)
    into available_coordinators
    from (
        select distinct ur.user_id
        from public.user_roles ur
        join public.roles ro on ro.role_id = ur.role_id
        where replace(lower(trim(ro.role_name)), ' ', '_') = 'event_coordinator'
    ) eligible
    join public.users u on u.user_id = eligible.user_id;

    return jsonb_build_object(
        'items', dashboard_items,
        'coordinators', available_coordinators
    );
end;
$function$;

REVOKE ALL ON FUNCTION "public"."event_coordinator_lead_dashboard"() FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.event_registration_roster (
  p_event_id integer
)
  RETURNS jsonb
  LANGUAGE plpgsql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare planned public.events;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not (public.has_booking_role('event_organiser') or public.has_booking_role('event_coordinator')) then
        return jsonb_build_object('error', 'Only event organisers and coordinators can view registration information.', 'status', 403);
    end if;
    select * into planned from public.events where event_id = p_event_id;
    if not found or (
        (public.has_booking_role('event_organiser') and planned.event_organiser_id = auth.uid())
        or (public.has_booking_role('event_coordinator') and planned.event_coordinator_id = auth.uid())
    ) is not true then
        return jsonb_build_object('error', 'Event not found or access unavailable.', 'status', 404);
    end if;
    return (select jsonb_build_object(
        'event', jsonb_build_object('event_id', planned.event_id, 'event_name', planned.event_name),
        'total_registered', count(*) filter (where r.status = 'registered'),
        'total_waitlisted', count(*) filter (where r.status = 'waiting_list'),
        'total_withdrawn', count(*) filter (where r.status = 'withdrawn'),
        'registrations', coalesce(jsonb_agg(jsonb_build_object(
            'attendee_id', r.attendee_id, 'full_name', r.full_name,
            'contact_email', r.contact_email, 'contact_phone', r.contact_phone,
            'status', r.status, 'registered_at', r.created_at, 'withdrawn_at', r.withdrawn_at
        ) order by r.created_at, r.attendee_id), '[]'::jsonb)
    ) from public.event_registration r where r.event_id = p_event_id);
end;
$function$;

REVOKE ALL ON FUNCTION "public"."event_registration_roster"(integer) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.event_request_assignment_queue()
  RETURNS jsonb
  LANGUAGE plpgsql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    requests jsonb;
    coordinators jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_coordinator_lead') then
        return jsonb_build_object(
            'error', 'Only Event Coordinator Leads can view unassigned event requests.',
            'status', 403
        );
    end if;

    select coalesce(jsonb_agg(
        jsonb_build_object(
            'event_request_id', r.event_request_id,
            'event_name', r.event_name,
            'purpose', r.purpose,
            'description', r.description,
            'start_datetime', r.start_datetime,
            'end_datetime', r.end_datetime,
            'capacity_needed', r.capacity_needed,
            'room_layout', r.room_layout,
            'event_organiser_name', coalesce(nullif(btrim(u.name), ''), nullif(btrim(u.email), ''))
        ) order by r.submitted_at, r.event_request_id
    ), '[]'::jsonb)
    into requests
    from public.event_request r
    left join public.users u on u.user_id = r.event_organiser_id
    where r.status = 'submitted'::public.event_status
      and r.event_coordinator_id is null;

    select coalesce(jsonb_agg(
        jsonb_build_object(
            'id', u.user_id,
            'name', coalesce(nullif(btrim(u.name), ''), nullif(btrim(u.email), ''), u.user_id::text)
        ) order by coalesce(nullif(btrim(u.name), ''), nullif(btrim(u.email), ''), u.user_id::text)
    ), '[]'::jsonb)
    into coordinators
    from (
        select distinct ur.user_id
        from public.user_roles ur
        join public.roles ro on ro.role_id = ur.role_id
        where replace(lower(trim(ro.role_name)), ' ', '_') = 'event_coordinator'
    ) assigned
    join public.users u on u.user_id = assigned.user_id;

    return jsonb_build_object('event_requests', requests, 'coordinators', coordinators);
end;
$function$;

REVOKE ALL ON FUNCTION "public"."event_request_assignment_queue"() FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.event_safety_check_blockers (
  p_event public.events
)
  RETURNS text[]
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare blockers text[]; requirements text[] := coalesce(p_event.safety_rework_arrangements, array[]::text[]);
begin
    blockers := public.event_confirmation_blockers(p_event);
    blockers := array_remove(blockers, 'An Event Coordinator must be assigned.');
    blockers := array_remove(blockers, 'The Event Coordinator must confirm registration readiness.');
    if p_event.safety_rework_required then
        blockers := array_append(blockers, 'Address the requested safety changes before another safety check.');
    end if;
    if 'venue' = any(requirements) and not exists (
        select 1 from public.venue_booking_requests b
        join public.venues v using (venue_id)
        where b.event_id = p_event.event_id and b.status = 'approved'
          and b.reviewed_at >= p_event.safety_rework_requested_at
          and b.starts_at = p_event.start_datetime and b.ends_at = p_event.end_datetime
          and (p_event.capacity_needed is null or b.attendance = p_event.capacity_needed)
          and v.deleted_at is null
          and cardinality(public.venue_shortfalls_for_event(v, p_event)) = 0
    ) then
        blockers := array_append(blockers, 'The affected venue arrangement must be reviewed and confirmed again.');
    end if;
    if 'technical' = any(requirements) and not exists (
        select 1 from public.equipment_reservations r
        where r.event_id = p_event.event_id
          and r.created_at >= p_event.safety_rework_requested_at
    ) then
        blockers := array_append(blockers, 'The affected technical arrangement must be reviewed and confirmed again.');
    end if;
    return coalesce(blockers, array[]::text[]);
end;
$function$;

REVOKE ALL ON FUNCTION "public"."event_safety_check_blockers"(public.events) FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.event_venue_bookings (
  p_event_id integer
)
  RETURNS jsonb
  LANGUAGE plpgsql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare planned public.events;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    select * into planned from public.events where event_id = p_event_id;
    if not found then
        return jsonb_build_object('error', 'Event not found or access unavailable.', 'status', 404);
    end if;
    if auth.uid() is distinct from planned.event_organiser_id
       and auth.uid() is distinct from planned.event_coordinator_id
       and auth.uid() is distinct from planned.technical_support_id
       and auth.uid() is distinct from planned.venue_staff_id
       and auth.uid() is distinct from planned.safety_officer_id then
        return jsonb_build_object('error', 'Only the people assigned to this event can view its venue bookings.', 'status', 403);
    end if;
    return jsonb_build_object('bookings', coalesce((
        select jsonb_agg(to_jsonb(b) || jsonb_build_object(
            'venue_name', v.venue_name,
            'reviewed_by_name', reviewer.name
        ) order by b.submitted_at desc)
        from public.venue_booking_requests b
        join public.venues v on v.venue_id = b.venue_id
        left join public.users reviewer on reviewer.user_id = b.reviewed_by
        where b.event_id = p_event_id
    ), '[]'::jsonb));
end;
$function$;

REVOKE ALL ON FUNCTION "public"."event_venue_bookings"(integer) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.expire_venue_holds()
  RETURNS void
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare held public.venue_booking_requests;
begin
    for held in
        select * from public.venue_booking_requests b
        where b.status = 'submitted' and b.hold_expires_at > now() and b.hold_expires_at <= now() + interval '24 hours'
          and not exists (select 1 from public.notifications n
                          where n.recipient_id = b.requested_by and n.kind = 'venue_hold_reminder'
                            and n.link = '/venue-bookings/' || b.booking_id
                            and n.created_at > b.hold_expires_at - interval '24 hours')
    loop
        perform public.notify_user(held.requested_by, 'venue_hold_reminder', 'Tentative hold expiring soon',
            format('Reminder: the tentative hold on %s for %s expires on %s SGT. Unless Venue Staff confirm the booking by then, the venue becomes available to other requests.',
                   coalesce((select venue_name from public.venues where venue_id = held.venue_id), 'the venue'),
                   coalesce(held.event_name, 'an unnamed event'),
                   to_char(held.hold_expires_at at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI')),
            '/venue-bookings/' || held.booking_id);
    end loop;

    update public.venue_booking_requests set status = 'expired', expired_at = now()
    where status = 'submitted' and hold_expires_at <= now();
end;
$function$;

REVOKE ALL ON FUNCTION "public"."expire_venue_holds"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.get_venue_booking (
  p_booking_id uuid
)
  RETURNS jsonb
  LANGUAGE plpgsql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare found_booking jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    select item into found_booking
    from public.visible_venue_bookings() as item
    where (item->>'booking_id')::uuid = p_booking_id;

    -- Not found and not permitted read the same, so a request's existence is
    -- not disclosed to someone who may not see it.
    if found_booking is null then
        return jsonb_build_object('error', 'Booking request not found or access unavailable.', 'status', 404);
    end if;
    return jsonb_build_object(
        'booking', found_booking,
        'can_review', public.has_booking_role('venue_staff')
    );
end;
$function$;

REVOKE ALL ON FUNCTION "public"."get_venue_booking"(uuid) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.guard_equipment_event()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
begin
    if TG_OP = 'DELETE' then
        delete from public.equipment_reservations
        where event_id = old.event_id;
        return old;
    end if;
    if exists (
        select 1 from public.equipment_reservations
        where event_id = old.event_id
    ) and (
        new.event_id is distinct from old.event_id
        or coalesce(to_jsonb(new)->>'start_datetime', to_jsonb(new)->>'starts_at')
            is distinct from coalesce(to_jsonb(old)->>'start_datetime', to_jsonb(old)->>'starts_at')
        or coalesce(to_jsonb(new)->>'end_datetime', to_jsonb(new)->>'ends_at')
            is distinct from coalesce(to_jsonb(old)->>'end_datetime', to_jsonb(old)->>'ends_at')
    ) then
        raise check_violation using message =
            'Cancel equipment reservations before changing event dates or deleting the event.';
    end if;
    return new;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."guard_equipment_event"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.guard_equipment_request_acceptance()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare ev public.events; booking public.equipment_reservations; model_type text;
begin
    if new.status in ('accepted','partially_accepted') then
        select * into ev from public.events where event_id::text=new.event_id::text for update;
        if not public.can_reserve_equipment() or ev.technical_support_id is distinct from auth.uid() then
            raise insufficient_privilege using message='Only assigned Technical Support Staff can accept this request.'; end if;
        select * into booking from public.equipment_reservations where equipment_request_id=new.equipment_request_id for update;
        if not found or booking.event_id::text <> new.event_id::text or booking.equipment_id is distinct from new.equipment_id
           or booking.quantity is distinct from new.accepted_quantity or booking.starts_at > ev.start_datetime
           or booking.ends_at < ev.end_datetime or ev.start_datetime is null or ev.end_datetime is null then
            raise check_violation using message='Reserve equipment linked to this request before accepting it.'; end if;
        select equipment_type into model_type from public.equipment where equipment_id=booking.equipment_id;
        if lower(btrim(model_type)) is distinct from lower(btrim(new.equipment_type))
           or new.accepted_quantity < 1 or new.accepted_quantity > new.quantity
           or (new.status='accepted' and new.accepted_quantity <> new.quantity)
           or (new.status='partially_accepted' and new.accepted_quantity >= new.quantity) then
            raise check_violation using message='Acceptance must match the reserved type and quantity.'; end if;
    end if;
    return new;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."guard_equipment_request_acceptance"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.guard_equipment_request_review()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SET search_path TO 'public'
  AS $function$
begin
    if current_user in ('authenticated', 'anon') then
        if tg_op = 'INSERT' then
            if new.status <> 'pending' or new.accepted_quantity is not null
                or new.reviewed_by is not null or new.reviewed_at is not null then
                raise exception 'Use the equipment review action to record a decision.';
            end if;
        elsif tg_op = 'DELETE' then
            if old.status <> 'pending' then raise exception 'Reviewed requests cannot be deleted directly.'; end if;
            return old;
        elsif old.status <> 'pending' or new.status <> 'pending'
            or new.accepted_quantity is distinct from old.accepted_quantity
            or new.reviewed_by is distinct from old.reviewed_by
            or new.reviewed_at is distinct from old.reviewed_at then
            raise exception 'Use the equipment review action to record a decision.';
        end if;
    end if;
    return new;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."guard_equipment_request_review"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.guard_event_lifecycle()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    blockers text[];
    change_request_workflow boolean := coalesce(current_setting('connectsphere.change_request_workflow', true), '') = 'true';
    non_important_workflow boolean := coalesce(current_setting('connectsphere.change_request_importance', true), '') = 'non_important';
    -- 048: set only by submit_event_for_safety_checks().
    safety_submission boolean := coalesce(current_setting('connectsphere.safety_submission', true), '') = 'true';
begin
    if TG_OP = 'INSERT' then
        new.registration_ready := false;
        if new.status <> 'planning' then
            raise check_violation using message = 'New operational events start in Planning.';
        end if;
    else
        if (new.safety_rework_required is distinct from old.safety_rework_required
            or new.safety_rework_requested_at is distinct from old.safety_rework_requested_at
            or new.safety_rework_arrangements is distinct from old.safety_rework_arrangements
            or new.safety_approved_at is distinct from old.safety_approved_at)
            and current_setting('connectsphere.safety_workflow', true) is distinct from 'true' then
            raise insufficient_privilege using message = 'Safety workflow fields can only be changed by the safety workflow.';
        end if;
        if old.status = 'confirmed' and not change_request_workflow and
            (to_jsonb(new) - array['status', 'registration_ready', 'updated_at',
                                   'safety_rework_required', 'safety_rework_requested_at',
                                   'safety_rework_arrangements', 'safety_approved_at']) is distinct from
            (to_jsonb(old) - array['status', 'registration_ready', 'updated_at',
                                   'safety_rework_required', 'safety_rework_requested_at',
                                   'safety_rework_arrangements', 'safety_approved_at']) then
            raise check_violation using message = 'Confirmed event arrangements cannot be edited.';
        end if;
        if new.registration_ready is distinct from old.registration_ready
            and auth.uid() is distinct from old.event_coordinator_id then
            raise insufficient_privilege using message = 'Only the assigned coordinator can confirm registration readiness.';
        end if;
        if new.registration_needs is distinct from old.registration_needs then
            new.registration_ready := false;
        end if;
        if (to_jsonb(new) - array['status', 'updated_at', 'registration_ready',
                                  'safety_rework_required', 'safety_rework_requested_at',
                                  'safety_rework_arrangements', 'safety_approved_at'])
                is distinct from
                (to_jsonb(old) - array['status', 'updated_at', 'registration_ready',
                                       'safety_rework_required', 'safety_rework_requested_at',
                                       'safety_rework_arrangements', 'safety_approved_at'])
            and not (change_request_workflow and non_important_workflow) then
            new.safety_rework_required := false;
            new.safety_approved_at := null;
        end if;
        if old.status in ('completed', 'cancelled') and new is distinct from old then
            raise check_violation using message = 'Completed and cancelled events cannot be changed.';
        end if;
        if new.status is distinct from old.status and not (
            (old.status = 'planning' and new.status = 'cancelled')
            -- 048: the coordinator's submission is the only way into the queue.
            or (old.status = 'planning' and new.status = 'pending_safety_checks' and safety_submission)
            or (old.status = 'pending_safety_checks' and new.status in ('planning', 'confirmed', 'cancelled'))
            or (old.status = 'confirmed' and new.status in ('planning', 'completed', 'cancelled'))
        ) then
            raise check_violation using message = 'Invalid event status transition.';
        end if;
        if old.status = 'pending_safety_checks' and new.status = 'confirmed' and not exists (
            select 1 from public.operational_safety_decision d
            where d.event_id = old.event_id and d.safety_officer_id = auth.uid()
              and d.outcome = 'approved' and d.created_at >= old.updated_at
        ) then
            raise insufficient_privilege using message = 'A Safety Officer approval is required before confirming this event.';
        end if;
        if new.status = 'cancelled' and old.status <> 'cancelled'
            and auth.uid() is distinct from old.event_coordinator_id
            and auth.uid() is distinct from old.event_organiser_id then
            raise insufficient_privilege using message = 'Only the organiser or coordinator can cancel an event.';
        end if;
        if new.status = 'completed' and old.status <> 'completed'
            and (new.end_datetime is null or new.end_datetime > now()) then
            raise check_violation using message = 'An event cannot complete before its end time.';
        end if;
    end if;
    if TG_OP = 'UPDATE' and change_request_workflow then
        new.status := old.status;
    elsif new.status in ('planning', 'pending_safety_checks') then
        blockers := public.event_safety_check_blockers(new);
        if cardinality(blockers) > 0 then
            new.status := 'planning'::public.event_status;
        elsif new.safety_approved_at is not null
            and cardinality(public.event_confirmation_blockers(new)) = 0 then
            new.status := 'confirmed'::public.event_status;
        end if;
        -- 048: otherwise the requested status stands. Planning is no longer
        -- promoted just because its arrangements are complete.
    elsif new.status = 'confirmed' and cardinality(public.event_confirmation_blockers(new)) > 0 then
        -- 048: only an event that still holds its safety approval waits in
        -- Pending Safety Checks; one whose approval was withdrawn goes back to
        -- Planning for the coordinator to submit again.
        new.status := case when new.safety_approved_at is not null
                                and cardinality(public.event_safety_check_blockers(new)) = 0
                           then 'pending_safety_checks'::public.event_status
                           else 'planning'::public.event_status end;
    end if;
    if TG_OP = 'UPDATE' then new.updated_at := clock_timestamp(); end if;
    return new;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."guard_event_lifecycle"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.guard_registration_settings()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
begin
    if row(new.registration_opens_at, new.registration_closes_at, new.waiting_list_enabled)
        is distinct from row(old.registration_opens_at, old.registration_closes_at, old.waiting_list_enabled) then
        if auth.uid() is null or auth.uid() is distinct from old.event_organiser_id
            or not public.has_booking_role('event_organiser') then
            raise insufficient_privilege using message = 'Only the assigned Event Organiser can manage registration.';
        end if;
        if old.status not in ('planning', 'pending_safety_checks', 'confirmed')
            or old.end_datetime <= clock_timestamp()
            or old.registration_closes_at <= clock_timestamp() then
            raise check_violation using message = 'Registration settings can only change before or during registration.';
        end if;
    end if;
    return new;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."guard_registration_settings"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.guard_request_lifecycle()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
begin
    if TG_OP = 'INSERT' then
        if new.status not in ('draft', 'submitted') then
            raise check_violation using message = 'New requests must be Draft or Submitted.';
        end if;
    elsif new.status is distinct from old.status then
        if not ((old.status = 'draft' and new.status in ('submitted', 'cancelled'))
            or (old.status = 'submitted' and new.status in ('planning', 'rejected', 'cancelled'))
            or (old.status = 'rejected' and new.status in ('submitted', 'cancelled'))) then
            raise check_violation using message = 'Invalid request status transition.';
        end if;
        if new.status in ('planning', 'rejected') then
            if auth.uid() is distinct from old.event_coordinator_id then
                raise insufficient_privilege using message = 'Only the assigned coordinator can decide a request.';
            end if;
            if not exists (select 1 from public.event_request_review r
                where r.event_request_id = new.event_request_id
                  and r.reviewer_id = old.event_coordinator_id
                  and r.outcome::text = case when new.status = 'planning' then 'approved' else 'rejected' end
                  and r.created_at >= old.updated_at) then
                raise check_violation using message = 'A matching coordinator review is required.';
            end if;
        end if;
    end if;
    if new.status = 'submitted' and (TG_OP = 'INSERT' or old.status is distinct from new.status)
        and (new.start_datetime <= now() or new.end_datetime <= new.start_datetime) then
        raise check_violation using message = 'Submission requires a future start and an end after the start.';
    end if;
    return new;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."guard_request_lifecycle"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.guard_reviewed_equipment_event()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
begin
    if exists (select 1 from public.equipment_request r where r.event_id = old.event_id
        and r.status in ('accepted', 'partially_accepted', 'in_progress', 'completed'))
        and (coalesce(to_jsonb(new)->>'start_datetime', to_jsonb(new)->>'starts_at')
             is distinct from coalesce(to_jsonb(old)->>'start_datetime', to_jsonb(old)->>'starts_at')
          or coalesce(to_jsonb(new)->>'end_datetime', to_jsonb(new)->>'ends_at')
             is distinct from coalesce(to_jsonb(old)->>'end_datetime', to_jsonb(old)->>'ends_at')) then
        raise exception 'Release accepted equipment requests before changing event dates.';
    end if;
    return new;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."guard_reviewed_equipment_event"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.handle_new_auth_user()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO ''
  AS $function$
begin
    insert into public.users (user_id, name, email)
    values (
        new.id,
        coalesce(
            nullif(btrim(new.raw_user_meta_data ->> 'name'), ''),
            nullif(split_part(coalesce(new.email, ''), '@', 1), ''),
            'user-' || left(new.id::text, 8)
        ),
        new.email
    )
    on conflict (user_id) do nothing;

    return new;
end;
$function$;

CREATE OR REPLACE FUNCTION public.has_booking_role (
  p_role text
)
  RETURNS boolean
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    select exists (select 1 from public.user_roles ur join public.roles r using (role_id)
        where ur.user_id = auth.uid()
        and replace(lower(trim(r.role_name)), ' ', '_') = p_role);
$function$;

REVOKE ALL ON FUNCTION "public"."has_booking_role"(text) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.has_safety_officer_role()
  RETURNS boolean
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    select auth.uid() is not null and exists (
        select 1
        from public.user_roles ur join public.roles r using (role_id)
        where ur.user_id = auth.uid()
          and lower(replace(btrim(r.role_name), ' ', '_')) = 'safety_officer'
    );
$function$;

REVOKE ALL ON FUNCTION "public"."has_safety_officer_role"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.hold_venue_booking (
  p_booking_id uuid,
  p_expires_at timestamp with time zone
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare booking public.venue_booking_requests;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('venue_staff') then
        return jsonb_build_object('error', 'Only Venue Staff can place a tentative hold.', 'status', 403);
    end if;
    select * into booking from public.venue_booking_requests where booking_id = p_booking_id for update;
    if not found then
        return jsonb_build_object('error', 'Booking request not found or access unavailable.', 'status', 404);
    end if;
    if booking.status <> 'submitted' or booking.hold_expires_at is not null then
        return jsonb_build_object('error', 'Only a pending request without a hold can be held.', 'status', 409);
    end if;
    if p_expires_at is null or p_expires_at <= now() or p_expires_at >= booking.starts_at then
        return jsonb_build_object('error', 'Choose an expiry in the future and before the booking starts.',
                                  'errors', jsonb_build_object('expires_at', 'A valid expiry is required.'), 'status', 400);
    end if;
    if jsonb_array_length(public.venue_booking_conflicts(booking.venue_id, booking.starts_at, booking.ends_at,
                                                         booking.booking_id, true)) > 0 then
        return jsonb_build_object('error', 'The venue is already booked, held or unavailable at this time.', 'status', 409);
    end if;
    update public.venue_booking_requests set hold_expires_at = p_expires_at
    where booking_id = p_booking_id returning * into booking;
    return jsonb_build_object('booking', to_jsonb(booking));
end;
$function$;

REVOKE ALL ON FUNCTION "public"."hold_venue_booking"(uuid, timestamp WITH time zone) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.list_my_notifications (
  p_limit  integer,
  p_offset integer DEFAULT 0,
  p_days   integer DEFAULT NULL::integer
)
  RETURNS jsonb
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    with mine as (
        select * from public.notifications
        where recipient_id = auth.uid()
          and (p_days is null or created_at > now() - make_interval(days => p_days))
    )
    select case when auth.uid() is null
        then jsonb_build_object('error', 'Please sign in again.', 'status', 401)
        else jsonb_build_object(
            'items', coalesce((select jsonb_agg(to_jsonb(page) - 'recipient_id' order by page.created_at desc)
                               from (select * from mine order by created_at desc
                                     limit least(greatest(p_limit, 1), 50) offset greatest(p_offset, 0)) page), '[]'::jsonb),
            'total', (select count(*) from mine),
            'unread', (select count(*) from public.notifications where recipient_id = auth.uid() and read_at is null))
    end;
$function$;

REVOKE ALL ON FUNCTION "public"."list_my_notifications"(integer, integer, integer) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.list_venue_bookings()
  RETURNS jsonb
  LANGUAGE plpgsql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare staff boolean := public.has_booking_role('venue_staff');
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not staff and not public.has_booking_role('event_coordinator') then
        return jsonb_build_object('error', 'Venue bookings are available to Event Coordinators and Venue Staff.', 'status', 403);
    end if;
    return jsonb_build_object(
        'bookings', coalesce((
            select jsonb_agg(item order by item->>'submitted_at' desc)
            from public.visible_venue_bookings() as item
        ), '[]'::jsonb),
        'can_submit', public.has_booking_role('event_coordinator'),
        'can_review', staff
    );
end;
$function$;

REVOKE ALL ON FUNCTION "public"."list_venue_bookings"() FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.mark_notification_read (
  p_notification_id bigint
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    update public.notifications set read_at = coalesce(read_at, now())
    where notification_id = p_notification_id and recipient_id = auth.uid();
    if not found then
        return jsonb_build_object('error', 'Notification not found.', 'status', 404);
    end if;
    return jsonb_build_object('notification_id', p_notification_id);
end;
$function$;

REVOKE ALL ON FUNCTION "public"."mark_notification_read"(bigint) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.modify_venue_booking (
  p_booking_id         uuid,
  p_venue_id           uuid,
  p_venue_requirements text
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    booking public.venue_booking_requests;
    planned public.events;
    chosen public.venues;
    shortfalls text[];
    blocking jsonb;
    notes text := trim(coalesce(p_venue_requirements, ''));
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_coordinator') then
        return jsonb_build_object('error', 'Only Event Coordinators can modify venue bookings.', 'status', 403);
    end if;

    select * into booking from public.venue_booking_requests
    where booking_id = p_booking_id and requested_by = auth.uid() for update;
    if not found then
        return jsonb_build_object('error', 'Booking request not found or access unavailable.', 'status', 404);
    end if;
    if booking.status not in ('submitted', 'approved') then
        return jsonb_build_object('error', 'Only pending or approved bookings can be modified.', 'status', 409);
    end if;

    select * into planned from public.events where event_id = booking.event_id;
    if not found or planned.status not in ('planning', 'pending_safety_checks')
        or planned.start_datetime <= now() then
        return jsonb_build_object('error', 'Bookings can only be modified before the event is confirmed and has started.', 'status', 409);
    end if;

    select * into chosen from public.venues where venue_id = p_venue_id and deleted_at is null;
    if not found then
        return jsonb_build_object('error', 'Select an existing venue.', 'status', 400);
    end if;
    if notes = '' or length(notes) > 5000 then
        return jsonb_build_object('error', 'Venue requirements are required (maximum 5000 characters).', 'status', 400);
    end if;

    shortfalls := public.venue_shortfalls_for_event(chosen, planned);
    if cardinality(shortfalls) > 0 then
        return jsonb_build_object('error', 'This venue does not meet the requirements recorded for this event.',
                                  'unmet_requirements', to_jsonb(shortfalls), 'status', 409);
    end if;
    blocking := public.venue_booking_conflicts(chosen.venue_id, planned.start_datetime,
                                               planned.end_datetime, booking.booking_id, true);
    if jsonb_array_length(blocking) > 0 then
        return jsonb_build_object('error', 'This venue is already booked for part of this event''s time.',
                                  'conflicts', blocking, 'status', 409);
    end if;
    if exists (select 1 from public.venue_blocks k where k.venue_id = chosen.venue_id
               and tstzrange(k.starts_at, k.ends_at, '[)')
                && tstzrange(planned.start_datetime, planned.end_datetime, '[)')) then
        return jsonb_build_object('error', 'This venue is blocked for part of this event''s time.', 'status', 409);
    end if;

    update public.venue_booking_requests
    set venue_id = chosen.venue_id, venue_requirements = notes, event_name = planned.event_name,
        starts_at = planned.start_datetime, ends_at = planned.end_datetime,
        attendance = coalesce(planned.capacity_needed, booking.attendance),
        status = 'submitted', reviewed_by = null, reviewed_at = null, review_comments = null,
        submitted_at = now()
    where booking_id = booking.booking_id
    returning * into booking;

    if planned.status = 'pending_safety_checks' then
        perform set_config('connectsphere.safety_workflow', 'true', true);
        update public.events
        set safety_rework_requested_at = clock_timestamp(), safety_rework_arrangements = array['venue'],
            safety_approved_at = null
        where event_id = planned.event_id;
    end if;
    return jsonb_build_object('booking', to_jsonb(booking));
end;
$function$;

REVOKE ALL ON FUNCTION "public"."modify_venue_booking"(uuid, uuid, text) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.my_equipment_request_events()
  RETURNS jsonb
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    select coalesce(jsonb_agg(jsonb_build_object('event_id', event_id::text, 'event_name', event_name)
        order by event_name), '[]'::jsonb)
    from public.events where public.can_reserve_equipment() and technical_support_id = auth.uid();
$function$;

REVOKE ALL ON FUNCTION "public"."my_equipment_request_events"() FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.my_equipment_reservations()
  RETURNS jsonb
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    select coalesce(jsonb_agg(jsonb_build_object(
        'reservation_id', r.reservation_id, 'event_id', r.event_id,
        'equipment_request_id', r.equipment_request_id,
        'event_name', e.event_name, 'equipment_id', r.equipment_id,
        'name', concat_ws(' - ', q.equipment_type, q.equipment_model),
        'quantity', r.quantity, 'starts_at', r.starts_at, 'ends_at', r.ends_at,
        'maximum_quantity', greatest(0, q.total_quantity -
            public.equipment_peak(r.equipment_id, r.starts_at, r.ends_at) + r.quantity)
    ) order by r.starts_at, r.created_at), '[]'::jsonb)
    from public.equipment_reservations r
    join public.equipment q on q.equipment_id = r.equipment_id
    join public.events e on e.event_id::text = r.event_id::text
    where r.created_by = auth.uid();
$function$;

REVOKE ALL ON FUNCTION "public"."my_equipment_reservations"() FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.my_event_registrations()
  RETURNS jsonb
  LANGUAGE plpgsql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('attendee') then
        return jsonb_build_object('error', 'Only attendees can view their registrations.', 'status', 403);
    end if;
    return (select jsonb_build_object('registrations', coalesce(jsonb_agg(
        jsonb_build_object(
            'event_id', e.event_id, 'event_name', e.event_name,
            'start_datetime', e.start_datetime, 'end_datetime', e.end_datetime,
            'event_status', e.status, 'status', r.status,
            'registered_at', r.created_at, 'withdrawn_at', r.withdrawn_at,
            'venues', coalesce((
                select jsonb_agg(distinct v.venue_name order by v.venue_name)
                from public.venues v
                where exists (select 1 from public.venue_booking_requests b
                    where b.event_id = e.event_id and b.venue_id = v.venue_id and b.status = 'approved')
                or (v.venue_id::text = to_jsonb(e)->>'venue_id'
                    and not exists (select 1 from public.venue_booking_requests b
                        where b.event_id = e.event_id and b.status = 'approved'))
            ), '[]'::jsonb)
        ) order by e.start_datetime desc nulls last, e.event_id desc
    ), '[]'::jsonb))
    from public.event_registration r
    join public.events e on e.event_id = r.event_id
    where r.attendee_id = auth.uid());
end;
$function$;

REVOKE ALL ON FUNCTION "public"."my_event_registrations"() FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.notify_coordinator_assignment()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    planned public.events;
    lead text := coalesce((select name from public.users where user_id = auth.uid()), 'an Event Coordinator Lead');
    item text;
begin
    if new.event_coordinator_id is not distinct from old.event_coordinator_id then
        return null;
    end if;
    select * into planned from public.events where event_request_id = new.event_request_id;
    -- An approved event may have been renamed since it was requested.
    item := format('%s by %s', coalesce(planned.event_name, new.event_name, 'an unnamed event'),
                   coalesce((select name from public.users where user_id = new.event_organiser_id), 'an Event Organiser'));

    if new.event_coordinator_id is not null then
        perform public.notify_user(new.event_coordinator_id, 'coordinator_assigned', 'Event assigned to you',
            case when planned.event_id is null
                then format('Event request %s has been %s to you by %s, pending review.', item,
                            case when old.event_coordinator_id is null then 'assigned' else 'reassigned' end, lead)
                else format('Event %s has been reassigned to you by %s. It is currently in %s.', item, lead,
                            replace(planned.status::text, '_', ' '))
            end,
            case when planned.event_id is null then '/review-event-requests/' || new.event_request_id
                 else '/events/' || planned.event_id end);
    end if;

    -- The previous coordinator can no longer open the item, so the link goes to their list.
    if old.event_coordinator_id is not null then
        perform public.notify_user(old.event_coordinator_id, 'coordinator_unassigned', 'Event reassigned',
            format('%s %s has been reassigned from you to %s by %s.',
                   case when planned.event_id is null then 'Event request' else 'Event' end, item,
                   coalesce((select name from public.users where user_id = new.event_coordinator_id), 'another Event Coordinator'),
                   lead),
            case when planned.event_id is null then '/review-event-requests' else '/events' end);
    end if;
    return null;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."notify_coordinator_assignment"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.notify_event_request_submitted()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    request text := coalesce(new.event_name, 'an unnamed event');
    latest public.event_request_review;
    reviewer text;
    event_link text;
begin
    if new.status = 'submitted' and (tg_op = 'INSERT' or old.status is distinct from 'submitted') then
        perform public.notify_role('event_coordinator_lead', 'event_request_submitted', 'New event request',
            format('Event request for %s by %s received and pending coordinator assignment.', request,
                   coalesce((select name from public.users where user_id = new.event_organiser_id), 'an Event Organiser')),
            '/assign-event-coordinators?request=' || new.event_request_id);
        perform public.notify_user(new.event_organiser_id, 'event_request_submitted', 'Event request submitted',
            format('Your event request %s has been submitted and is awaiting review.', request),
            '/event-requests/' || new.event_request_id);
    elsif tg_op = 'UPDATE' and new.status in ('planning', 'rejected') and old.status is distinct from new.status then
        select * into latest from public.event_request_review
        where event_request_id = new.event_request_id order by created_at desc, review_id desc limit 1;
        reviewer := coalesce((select name from public.users
                              where user_id = coalesce(latest.reviewer_id, new.event_coordinator_id)), 'the Event Coordinator');
        if new.status = 'planning' then
            select '/events/' || event_id into event_link from public.events where event_request_id = new.event_request_id;
            perform public.notify_user(new.event_organiser_id, 'event_request_approved', 'Event request approved',
                format('Your event request %s has been approved by %s. It is now in planning.', request, reviewer),
                coalesce(event_link, '/event-requests/' || new.event_request_id));
        else
            perform public.notify_user(new.event_organiser_id, 'event_request_rejected', 'Event request rejected',
                format('Your event request %s has been rejected by %s. Reason: %s', request, reviewer,
                       coalesce(latest.comments, 'none given')),
                '/event-requests/' || new.event_request_id);
        end if;
    end if;
    return null;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."notify_event_request_submitted"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.notify_event_staff_assigned()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    coordinator text := coalesce((select name from public.users where user_id = new.event_coordinator_id), 'not assigned');
    details text := format('%s by %s (%s – %s SGT)', coalesce(new.event_name, 'an unnamed event'),
        coalesce((select name from public.users where user_id = new.event_organiser_id), 'an Event Organiser'),
        to_char(new.start_datetime at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'),
        to_char(new.end_datetime at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'));
    staff record;
    assigned text[] := '{}';
begin
    for staff in select * from (values
        (new.venue_staff_id, 'Venue Staff', '/events/' || new.event_id),
        (new.technical_support_id, 'Technical Support', '/events/' || new.event_id),
        (new.safety_officer_id, 'Safety Officer', '/events/' || new.event_id)) as s(user_id, role, link)
    loop
        assigned := assigned || format('%s %s', staff.role,
            coalesce((select name from public.users where user_id = staff.user_id), 'not assigned'));
        if staff.user_id is not null then
            perform public.notify_user(staff.user_id, 'event_staff_assigned', 'Event assigned to you',
                format('Event %s has been assigned to you as %s. Event Coordinator: %s.', details, staff.role, coordinator),
                staff.link);
        end if;
    end loop;
    if new.event_coordinator_id is not null
       and coalesce(new.venue_staff_id, new.technical_support_id, new.safety_officer_id) is not null then
        perform public.notify_user(new.event_coordinator_id, 'event_staff_assigned', 'Staff assigned to your event',
            format('Staff assigned to %s: %s.', coalesce(new.event_name, 'an unnamed event'), array_to_string(assigned, ', ')),
            '/events/' || new.event_id);
    end if;
    return null;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."notify_event_staff_assigned"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.notify_role (
  p_role  text,
  p_kind  text,
  p_title text,
  p_body  text,
  p_link  text DEFAULT NULL::text
)
  RETURNS void
  LANGUAGE sql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    insert into public.notifications (recipient_id, kind, title, body, link)
    select distinct ur.user_id, p_kind, p_title, p_body, p_link
    from public.user_roles ur join public.roles r using (role_id)
    join auth.users u on u.id = ur.user_id
    where replace(lower(trim(r.role_name)), ' ', '_') = p_role;
$function$;

REVOKE ALL ON FUNCTION "public"."notify_role"(text, text, text, text, text) FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.notify_user (
  p_recipient uuid,
  p_kind      text,
  p_title     text,
  p_body      text,
  p_link      text DEFAULT NULL::text
)
  RETURNS void
  LANGUAGE sql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    insert into public.notifications (recipient_id, kind, title, body, link)
    select p_recipient, p_kind, p_title, p_body, p_link
    where exists (select 1 from auth.users where id = p_recipient);
$function$;

REVOKE ALL ON FUNCTION "public"."notify_user"(uuid, text, text, text, text) FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.notify_venue_booking_change()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    venue text := coalesce((select venue_name from public.venues where venue_id = new.venue_id), 'the venue');
    booking text := format('%s for %s (%s – %s SGT)', venue, coalesce(new.event_name, 'an unnamed event'),
        to_char(new.starts_at at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'),
        to_char(new.ends_at at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'));
    expiry text := to_char(new.hold_expires_at at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI');
    link text := '/venue-bookings/' || new.booking_id;
    block public.venue_blocks;
begin
    if tg_op = 'INSERT' then
        if new.status = 'submitted' then
            perform public.notify_user(new.requested_by, 'venue_booking_submitted', 'Venue booking request submitted',
                format('Your venue booking request for %s has been submitted. Status: pending Venue Staff review.', booking), link);
            perform public.notify_user((select venue_staff_id from public.events where event_id = new.event_id),
                'venue_booking_submitted', 'New venue booking request',
                format('%s has requested %s. Status: pending review.',
                       coalesce((select name from public.users where user_id = new.requested_by), 'An Event Coordinator'), booking),
                '/review-venue-bookings/' || new.booking_id);
        end if;
    elsif new.status is distinct from old.status then
        if old.status = 'submitted' and new.status in ('approved', 'rejected') then
            perform public.notify_user(new.requested_by, 'venue_booking_' || new.status, 'Venue booking ' || new.status,
                format('Your venue booking request for %s has been %s by %s.%s', booking, new.status,
                       coalesce((select name from public.users where user_id = new.reviewed_by), 'Venue Staff'),
                       case when new.status = 'rejected' then ' Reason: ' || coalesce(new.review_comments, 'none given') else '' end),
                link);
        elsif new.status = 'cancelled' and new.cancellation_reason like 'Venue unavailable: %' then
            select * into block from public.venue_blocks k
            where k.venue_id = new.venue_id
              and tstzrange(k.starts_at, k.ends_at, '[)') && tstzrange(new.occupied_from, new.occupied_until, '[)')
            order by k.created_at desc limit 1;
            perform public.notify_user(new.requested_by, 'venue_unavailable', 'Venue unavailable',
                format('%s is unavailable from %s to %s SGT (%s), which affects your %s %s. It has been cancelled.', venue,
                       to_char(block.starts_at at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'),
                       to_char(block.ends_at at time zone 'Asia/Singapore', 'DD Mon YYYY HH24:MI'), block.reason,
                       case when old.status = 'approved' then 'approved booking of' else 'pending booking request for' end, booking),
                link);
        elsif old.status = 'submitted' and new.status = 'expired' then
            perform public.notify_user(new.requested_by, 'venue_hold_expired', 'Tentative hold expired',
                format('The tentative hold on %s expired on %s SGT. The venue is now available to other requests.', booking, expiry),
                link);
        end if;
    elsif old.hold_expires_at is null and new.hold_expires_at is not null and new.status = 'submitted' then
        perform public.notify_user(new.requested_by, 'venue_hold_placed', 'Tentative hold placed',
            format('Venue Staff have placed a tentative hold on %s. It expires on %s SGT.', booking, expiry), link);
    end if;
    return null;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."notify_venue_booking_change"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.random_user_with_role (
  p_roles text[]
)
  RETURNS uuid
  LANGUAGE sql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    select ur.user_id
    from public.user_roles ur
    join public.roles r using (role_id)
    where replace(lower(btrim(r.role_name)), ' ', '_') = any(p_roles)
    order by random()
    limit 1;
$function$;

REVOKE ALL ON FUNCTION "public"."random_user_with_role"(text[]) FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.reassign_event_coordinator_for_lead (
  p_event_id       integer,
  p_coordinator_id uuid
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    assigned_event public.events;
    previous_coordinator_id uuid;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_coordinator_lead') then
        return jsonb_build_object(
            'error', 'Only Event Coordinator Leads can reassign events.',
            'status', 403
        );
    end if;
    if p_coordinator_id is null or not exists (
        select 1
        from public.user_roles ur
        join public.roles ro on ro.role_id = ur.role_id
        where ur.user_id = p_coordinator_id
          and replace(lower(trim(ro.role_name)), ' ', '_') = 'event_coordinator'
    ) then
        return jsonb_build_object(
            'error', 'Choose a user with the Event Coordinator role.',
            'status', 400
        );
    end if;

    select * into assigned_event
    from public.events
    where event_id = p_event_id
    for update;

    if not found then
        return jsonb_build_object('error', 'Event not found.', 'status', 404);
    end if;
    if assigned_event.status::text not in (
        'planning',
        'pending_safety_checks',
        'confirmed'
    ) then
        return jsonb_build_object(
            'error', 'This event is no longer available for reassignment.',
            'status', 409
        );
    end if;

    previous_coordinator_id := assigned_event.event_coordinator_id;
    if previous_coordinator_id is distinct from p_coordinator_id then
        update public.events
        set event_coordinator_id = p_coordinator_id
        where event_id = p_event_id
        returning * into assigned_event;

        if assigned_event.event_request_id is not null then
            update public.event_request
            set event_coordinator_id = p_coordinator_id,
                updated_at = now()
            where event_request_id = assigned_event.event_request_id;

        end if;
    end if;

    return jsonb_build_object(
        'message', 'Event Coordinator reassigned successfully.',
        'event', to_jsonb(assigned_event)
    );
end;
$function$;

REVOKE ALL ON FUNCTION "public"."reassign_event_coordinator_for_lead"(integer, uuid) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.reassign_submitted_request_coordinator (
  p_event_request_id bigint,
  p_coordinator_id   uuid
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    assigned_request public.event_request;
    previous_coordinator_id uuid;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_coordinator_lead') then
        return jsonb_build_object(
            'error', 'Only Event Coordinator Leads can reassign event coordinators.',
            'status', 403
        );
    end if;
    if p_coordinator_id is null or not exists (
        select 1
        from public.user_roles ur
        join public.roles ro on ro.role_id = ur.role_id
        where ur.user_id = p_coordinator_id
          and replace(lower(trim(ro.role_name)), ' ', '_') = 'event_coordinator'
    ) then
        return jsonb_build_object(
            'error', 'Choose a user with the Event Coordinator role.',
            'status', 400
        );
    end if;

    select * into assigned_request
    from public.event_request
    where event_request_id = p_event_request_id
    for update;

    if not found then
        return jsonb_build_object('error', 'Event request not found.', 'status', 404);
    end if;
    if assigned_request.status <> 'submitted'::public.event_status then
        return jsonb_build_object(
            'error', 'Only submitted event requests can be reassigned.',
            'status', 409
        );
    end if;

    previous_coordinator_id := assigned_request.event_coordinator_id;
    if previous_coordinator_id is distinct from p_coordinator_id then
        update public.event_request
        set event_coordinator_id = p_coordinator_id,
            updated_at = now()
        where event_request_id = p_event_request_id
        returning * into assigned_request;

    end if;

    return jsonb_build_object(
        'message', 'Event Coordinator reassigned successfully.',
        'event_request', to_jsonb(assigned_request)
    );
end;
$function$;

REVOKE ALL ON FUNCTION "public"."reassign_submitted_request_coordinator"(bigint, uuid) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.record_event_status_change()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
begin
    insert into public.event_activity (event_id, changed_by, change_type, changes)
    values (new.event_id, auth.uid(), 'status_change',
        jsonb_build_object('status', jsonb_build_object('from', old.status, 'to', new.status)));
    return null;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."record_event_status_change"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.record_safety_decision (
  p_event_id              integer,
  p_outcome               text,
  p_remarks               text,
  p_affected_arrangements text[]
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare planned public.events; saved public.operational_safety_decision; outcome text := lower(btrim(coalesce(p_outcome, '')));
        remarks text := nullif(btrim(coalesce(p_remarks, '')), ''); affected text[] := coalesce(p_affected_arrangements, array[]::text[]); note text;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_safety_officer_role() then return jsonb_build_object('error', 'Only Safety Officers can record operational safety decisions.', 'status', 403); end if;
    if outcome not in ('approved', 'rejected', 'changes_requested') then return jsonb_build_object('error', 'Choose Approve, Reject, or Request changes.', 'status', 400); end if;
    if outcome <> 'approved' and remarks is null then return jsonb_build_object('error', 'Remarks are required when rejecting or requesting changes.', 'status', 400); end if;
    if remarks is not null and length(remarks) > 2000 then return jsonb_build_object('error', 'Remarks must be 2000 characters or fewer.', 'status', 400); end if;
    if not (affected <@ array['venue', 'technical']::text[]) then return jsonb_build_object('error', 'Affected arrangements must be venue or technical.', 'status', 400); end if;

    select * into planned from public.events where event_id = p_event_id for update;
    if not found or planned.status <> 'pending_safety_checks' then return jsonb_build_object('error', 'Event not found or no longer awaiting safety checks.', 'status', 404); end if;
    if outcome = 'approved' and cardinality(public.event_safety_check_blockers(planned)) > 0 then
        return jsonb_build_object('error', 'The event arrangements changed and must be completed before approval.', 'status', 409);
    end if;
    if planned.event_coordinator_id is null then return jsonb_build_object('error', 'Assign an Event Coordinator before recording a safety decision.', 'status', 409); end if;

    insert into public.operational_safety_decision (event_id, safety_officer_id, outcome, remarks, affected_arrangements)
    values (planned.event_id, auth.uid(), outcome, remarks, affected) returning * into saved;
    perform set_config('connectsphere.safety_workflow', 'true', true);
    if outcome = 'approved' then
        update public.events set status = 'confirmed', safety_rework_required = false,
            safety_rework_arrangements = array[]::text[], safety_approved_at = saved.created_at
        where event_id = planned.event_id returning * into planned;
        note := case when planned.status = 'confirmed' then 'Safety arrangements approved. The event is confirmed.'
                     else 'Safety arrangements approved. The event will be confirmed once its remaining readiness checks are complete.' end;
    else
        update public.events set status = 'planning', safety_rework_required = true,
            safety_rework_requested_at = saved.created_at, safety_rework_arrangements = affected,
            safety_approved_at = null
        where event_id = planned.event_id returning * into planned;
        note := case when outcome = 'rejected' then 'Safety arrangements rejected. Address the remarks before proceeding.'
                     else 'Safety changes requested. Address the remarks before proceeding.' end;
    end if;
    return jsonb_build_object('event', to_jsonb(planned), 'decision', to_jsonb(saved), 'message', note);
end;
$function$;

REVOKE ALL ON FUNCTION "public"."record_safety_decision"(integer, text, text, text[]) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.refresh_arranged_event()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare previous_id text; next_id text;
begin
    if TG_OP <> 'INSERT' then previous_id := old.event_id::text; end if;
    if TG_OP <> 'DELETE' then next_id := new.event_id::text; end if;
    -- This trigger is a trusted workflow write. A changed arrangement must be
    -- checked by Safety again, even if the event was previously confirmed.
    perform set_config('connectsphere.safety_workflow', 'true', true);
    update public.events set updated_at = clock_timestamp(), safety_rework_required = false,
        safety_approved_at = null
    where event_id::text in (previous_id, next_id)
      and status in ('planning', 'pending_safety_checks', 'confirmed');
    return null;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."refresh_arranged_event"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.refresh_venue_event_statuses()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
begin
    update public.events e set updated_at = clock_timestamp()
    where e.status in ('planning', 'confirmed') and exists (
        select 1 from public.venue_booking_requests b
        where b.event_id = e.event_id and b.venue_id = new.venue_id and b.status = 'approved'
    );
    return null;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."refresh_venue_event_statuses"() FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.refresh_visible_event_statuses()
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    update public.events set status = 'completed'
    where status = 'confirmed' and end_datetime <= now()
      and auth.uid() in (event_organiser_id, event_coordinator_id, technical_support_id, venue_staff_id);
    return '{}'::jsonb;
end;
$function$;

REVOKE ALL ON FUNCTION "public"."refresh_visible_event_statuses"() FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.register_for_event (
  p_event_id      integer,
  p_full_name     text,
  p_contact_email text,
  p_contact_phone text
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    declare planned public.events; saved public.event_registration; total integer; instant timestamptz;
    begin
        if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_booking_role('attendee') then
        return jsonb_build_object('error', 'Only attendees can register for events.', 'status', 403);
    end if;
        if p_full_name is null or length(btrim(p_full_name)) not between 1 and 150
            or p_full_name ~ '[[:cntrl:]]'
            or p_contact_email is null or length(btrim(p_contact_email)) > 254
            or btrim(p_contact_email) !~ '^[A-Za-z0-9.!#$%&''*+/=?^_`{|}~-]+@[A-Za-z0-9-]+([.][A-Za-z0-9-]+)+$'
            or p_contact_phone is null or length(btrim(p_contact_phone)) > 30
            or btrim(p_contact_phone) !~ '^\+?[0-9 ()-]{7,30}$'
            or length(regexp_replace(p_contact_phone, '[^0-9]', '', 'g')) < 7 then
            return jsonb_build_object('error', 'Provide a valid full name, contact email and phone number.', 'status', 400);
        end if;
        -- The same lock serialises registrations and period edits. Read the clock
        -- after acquiring it so requests waiting across closing time are refused.
        select * into planned from public.events where event_id = p_event_id for update;
        instant := clock_timestamp();
        if not found or planned.status <> 'confirmed' or planned.end_datetime <= instant
            or planned.registration_opens_at is null then
            return jsonb_build_object('error', 'Registration is unavailable for this event.', 'status', 409);
        end if;
        if instant < planned.registration_opens_at then
            return jsonb_build_object('error', 'Registration is not yet open.', 'status', 409);
        end if;
        if instant >= planned.registration_closes_at then
            return jsonb_build_object('error', 'Registration has closed.', 'status', 409);
        end if;
        select * into saved from public.event_registration
            where event_id = p_event_id and attendee_id = auth.uid();
        if found and saved.status <> 'withdrawn' then
            return jsonb_build_object('registration', to_jsonb(saved), 'notification',
                coalesce((select case when sent_at is null then 'queued' else 'sent' end
                    from public.registration_email_outbox where event_id = p_event_id and attendee_id = auth.uid()), 'unavailable'));
        end if;
        select count(*) into total from public.event_registration
            where event_id = p_event_id and status = 'registered';
        if planned.capacity_needed is null or planned.capacity_needed < 1 then
            return jsonb_build_object('error', 'Registration capacity is not configured.', 'status', 409);
        end if;
        if total >= planned.capacity_needed and not planned.waiting_list_enabled then
            return jsonb_build_object('error', 'This event is full. The waiting list is disabled.', 'status', 409);
        end if;
        insert into public.event_registration(event_id, attendee_id, status, full_name, contact_email, contact_phone)
        values (p_event_id, auth.uid(), case when total >= planned.capacity_needed then 'waiting_list' else 'registered' end, btrim(p_full_name), btrim(p_contact_email), btrim(p_contact_phone))
        on conflict (event_id, attendee_id) do update set
            status = excluded.status, full_name = excluded.full_name,
            contact_email = excluded.contact_email, contact_phone = excluded.contact_phone,
            created_at = clock_timestamp(), withdrawn_at = null
        returning * into saved;
        insert into public.registration_email_outbox(event_id, attendee_id, recipient, subject, body)
        values (p_event_id, auth.uid(), saved.contact_email,
            case when saved.status = 'registered' then 'Event registration confirmed' else 'Event waiting list confirmation' end,
            'Hello ' || saved.full_name || E',\n\n' ||
            case when saved.status = 'registered' then 'Your registration is confirmed for ' else 'You have joined the waiting list for ' end ||
            planned.event_name || E'.\n' ||
            case when saved.status = 'waiting_list' then 'This does not confirm a place at the event.' else 'We look forward to seeing you.' end)
        on conflict (event_id, attendee_id) do update set
            recipient = excluded.recipient, subject = excluded.subject, body = excluded.body,
            created_at = clock_timestamp(), sent_at = null;
        return jsonb_build_object('registration', to_jsonb(saved), 'notification', 'queued');
    end;
    $function$;

REVOKE ALL ON FUNCTION "public"."register_for_event"(integer, text, text, text) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.release_venue_hold (
  p_booking_id uuid
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare booking public.venue_booking_requests;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('venue_staff') then
        return jsonb_build_object('error', 'Only Venue Staff can release a tentative hold.', 'status', 403);
    end if;
    update public.venue_booking_requests set hold_expires_at = null
    where booking_id = p_booking_id and status = 'submitted' and hold_expires_at > now()
    returning * into booking;
    if not found then
        return jsonb_build_object('error', 'This request has no active hold.', 'status', 409);
    end if;
    return jsonb_build_object('booking', to_jsonb(booking));
end;
$function$;

REVOKE ALL ON FUNCTION "public"."release_venue_hold"(uuid) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.reservable_equipment_events()
  RETURNS jsonb
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    select coalesce(jsonb_agg(jsonb_build_object(
        'event_id', e.event_id::text, 'event_name', e.event_name
    ) order by e.event_name), '[]'::jsonb)
    from public.events e
    where auth.uid() is not null
      and to_jsonb(e)->>'technical_support_id' = auth.uid()::text;
$function$;

REVOKE ALL ON FUNCTION "public"."reservable_equipment_events"() FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.reserve_equipment (
  p_event_id     text,
  p_equipment_id integer,
  p_quantity     integer
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.can_reserve_equipment() then
        return jsonb_build_object('error', 'Only Technical Support Staff can reserve equipment.', 'status', 403);
    end if;
    return public.reserve_equipment_assigned(p_event_id, p_equipment_id, p_quantity);
end;
$function$;

REVOKE ALL ON FUNCTION "public"."reserve_equipment"(text, integer, integer) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.reserve_equipment_assigned (
  p_event_id     text,
  p_equipment_id integer,
  p_quantity     integer
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    ev jsonb; reservation_event_id public.equipment_reservations.event_id%type; s timestamptz; f timestamptz; stock integer;
    available bigint; saved public.equipment_reservations;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if p_quantity is null or p_quantity <= 0 then
        return jsonb_build_object('error', 'Quantity must be a positive whole number.', 'status', 400);
    end if;
    select to_jsonb(e) into ev from public.events e where e.event_id::text = p_event_id for update;
    if ev is null then return jsonb_build_object('error', 'Event not found.', 'status', 404); end if;
    if ev->>'technical_support_id' is distinct from auth.uid()::text then
        return jsonb_build_object('error', 'Only the assigned Technical Support Staff can reserve equipment for this event.', 'status', 403);
    end if;
    s := coalesce(ev->>'start_datetime', ev->>'starts_at')::timestamptz;
    f := coalesce(ev->>'end_datetime', ev->>'ends_at')::timestamptz;
    if s is null or f is null or f <= s then
        return jsonb_build_object('error', 'Set valid event dates before reserving equipment.', 'status', 400);
    end if;
    -- Stock row lock serializes all writers sharing equipment_peak, including
    -- accepted equipment requests and reservation quantity changes.
    select total_quantity into stock from public.equipment where equipment_id = p_equipment_id for update;
    if not found then return jsonb_build_object('error', 'Equipment not found.', 'status', 404); end if;
    if exists (select 1 from public.equipment_reservations
        where event_id::text = p_event_id and equipment_id = p_equipment_id and equipment_request_id is null) then
        return jsonb_build_object('error', 'This equipment is already reserved directly for this event. Update the existing reservation instead.', 'status', 409);
    end if;
    -- Same calculation as equipment_window_availability and equipment_availability.
    -- Half-open windows: an event ending at the next event's start does not overlap.
    available := greatest(0, stock - public.equipment_peak(p_equipment_id, s, f));
    if p_quantity > available then
        return jsonb_build_object('error', format('Insufficient equipment: only %s available for this event.', available),
            'available_quantity', available, 'status', 409);
    end if;
    -- Assign the validated event ID using the actual reservation column type.
    -- PL/pgSQL assignment supports either legacy text or integer columns.
    reservation_event_id := ev->>'event_id';
    insert into public.equipment_reservations(event_id, equipment_id, quantity, starts_at, ends_at, created_by)
    values (reservation_event_id, p_equipment_id, p_quantity, s, f, auth.uid()) returning * into saved;
    return jsonb_build_object('reservation', to_jsonb(saved), 'message', 'Equipment reserved successfully.');
end;
$function$;

REVOKE ALL ON FUNCTION "public"."reserve_equipment_assigned"(text, integer, integer) FROM PUBLIC, "anon", "authenticated";

CREATE OR REPLACE FUNCTION public.reserve_equipment_for_request (
  p_request_id   integer,
  p_equipment_id integer,
  p_quantity     integer
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare req public.equipment_request; ev public.events; stock public.equipment;
    booking public.equipment_reservations; event_key public.equipment_reservations.event_id%type; available bigint;
begin
    if auth.uid() is null then return jsonb_build_object('error','Please sign in again.','status',401); end if;
    if not public.can_reserve_equipment() then return jsonb_build_object('error','Only Technical Support Staff can reserve equipment.','status',403); end if;
    select * into req from public.equipment_request where equipment_request_id=p_request_id;
    if not found then return jsonb_build_object('error','Request not found.','status',404); end if;
    -- Shared write lock order: event, stock, request, reservation.
    select * into ev from public.events where event_id::text=req.event_id::text for update;
    if not found or ev.technical_support_id is distinct from auth.uid() then
        return jsonb_build_object('error','Only the assigned Technical Support Staff can reserve for this request.','status',403); end if;
    if ev.status::text <> 'planning' then return jsonb_build_object('error','Equipment can only be reserved during planning.','status',409); end if;
    select * into stock from public.equipment where equipment_id=p_equipment_id for update;
    if not found then return jsonb_build_object('error','Select valid equipment.','status',400); end if;
    select * into req from public.equipment_request where equipment_request_id=p_request_id for update;
    if req.event_id::text <> ev.event_id::text or req.status <> 'pending' then
        return jsonb_build_object('error','Only pending requests can be reserved. Refresh the page.','status',409); end if;
    if p_quantity is null or p_quantity < 1 or p_quantity > req.quantity then
        return jsonb_build_object('error','Reserve a positive quantity up to the requested quantity.','status',400); end if;
    if lower(btrim(stock.equipment_type)) <> lower(btrim(req.equipment_type)) then
        return jsonb_build_object('error','Select equipment matching the requested type.','status',400); end if;
    if ev.start_datetime is null or ev.end_datetime is null or ev.end_datetime <= ev.start_datetime then
        return jsonb_build_object('error','Valid event dates are required.','status',409); end if;
    if exists(select 1 from public.equipment_reservations where equipment_request_id=p_request_id) then
        return jsonb_build_object('error','This request already has a reservation. Update or cancel it first.','status',409); end if;
    available := greatest(0, stock.total_quantity-public.equipment_peak(p_equipment_id,ev.start_datetime,ev.end_datetime));
    if p_quantity > available then return jsonb_build_object('error',format('Only %s available.',available),'status',409); end if;
    event_key := ev.event_id;
    insert into public.equipment_reservations(event_id,equipment_id,equipment_request_id,quantity,starts_at,ends_at,created_by)
    values(event_key,p_equipment_id,p_request_id,p_quantity,ev.start_datetime,ev.end_datetime,auth.uid()) returning * into booking;
    return jsonb_build_object('reservation',to_jsonb(booking),'equipment_request',to_jsonb(req),
        'message','Equipment reserved. The request is still pending; accept it separately.');
end;
$function$;

REVOKE ALL ON FUNCTION "public"."reserve_equipment_for_request"(integer, integer, integer) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.review_equipment_request (
  p_request_id        integer,
  p_outcome           text,
  p_equipment_id      integer,
  p_accepted_quantity integer,
  p_reason            text
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare req public.equipment_request; ev public.events; booking public.equipment_reservations; amount integer;
begin
    if auth.uid() is null then return jsonb_build_object('error','Please sign in again.','status',401); end if;
    select * into req from public.equipment_request where equipment_request_id=p_request_id;
    if not found then return jsonb_build_object('error','Request not found.','status',404); end if;
    select * into ev from public.events where event_id::text=req.event_id::text for update;
    if not public.can_reserve_equipment() or ev.technical_support_id is distinct from auth.uid() then
        return jsonb_build_object('error','Only the assigned Technical Support Staff can review this request.','status',403); end if;
    select * into req from public.equipment_request where equipment_request_id=p_request_id for update;
    if req.status <> 'pending' or req.event_id::text <> ev.event_id::text then
        return jsonb_build_object('error','This request has already been reviewed or changed.','status',409); end if;
    if p_outcome is null or p_outcome not in ('accepted','partially_accepted','rejected') then
        return jsonb_build_object('error','Choose a valid decision.','status',400); end if;
    select * into booking from public.equipment_reservations where equipment_request_id=p_request_id for update;
    if p_outcome='rejected' then
        if nullif(btrim(p_reason),'') is null then return jsonb_build_object('error','Enter a reason for rejection.','status',400); end if;
        if booking.reservation_id is not null then return jsonb_build_object('error','Cancel the linked reservation before rejecting this request.','status',409); end if;
        amount := 0;
    else
        amount := case when p_outcome='accepted' then req.quantity else p_accepted_quantity end;
        if booking.reservation_id is null or booking.equipment_id is distinct from p_equipment_id
           or booking.quantity is distinct from amount or booking.event_id::text <> req.event_id::text
           or booking.starts_at > ev.start_datetime or booking.ends_at < ev.end_datetime then
            return jsonb_build_object('error','Reserve matching equipment linked to this request before accepting it.','status',409); end if;
        if amount is null or amount < 1 or amount > req.quantity or (p_outcome='partially_accepted' and amount>=req.quantity) then
            return jsonb_build_object('error','Accepted quantity must match a valid full or partial reservation.','status',400); end if;
    end if;
    update public.equipment_request set status=p_outcome, accepted_quantity=amount,
        equipment_id=case when p_outcome='rejected' then null else booking.equipment_id end,
        reviewed_by=auth.uid(),reviewed_at=now(),
        reason_for_rejection=case when p_outcome='rejected' then btrim(p_reason) else null end
    where equipment_request_id=p_request_id returning * into req;
    return jsonb_build_object('equipment_request',to_jsonb(req),'reservation',to_jsonb(booking),'message','Decision recorded.');
end;
$function$;

REVOKE ALL ON FUNCTION "public"."review_equipment_request"(integer, text, integer, integer, text) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.review_event_change_request (
  p_request_id bigint,
  p_decision   text,
  p_reason     text   DEFAULT NULL::text
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    change_request public.event_change_request;
    planned public.events;
    candidate public.events;
    decision text := lower(btrim(coalesce(p_decision, '')));
    decision_reason_value text := nullif(btrim(coalesce(p_reason, '')), '');
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_booking_role('event_coordinator') then return jsonb_build_object('error', 'Only Event Coordinators can review event change requests.', 'status', 403); end if;
    if decision not in ('approve', 'reject') then return jsonb_build_object('error', 'Choose Approve or Reject.', 'status', 400); end if;
    if decision = 'reject' and decision_reason_value is null then return jsonb_build_object('error', 'Check the review decision.', 'errors', jsonb_build_object('reason', 'Please provide a reason for rejecting this change request.'), 'status', 400); end if;
    if decision_reason_value is not null and length(decision_reason_value) > 2000 then return jsonb_build_object('error', 'The decision reason must be 2000 characters or fewer.', 'status', 400); end if;

    select * into change_request from public.event_change_request where event_change_request_id = p_request_id for update;
    if not found then return jsonb_build_object('error', 'Change request not found or access unavailable.', 'status', 404); end if;
    select * into planned from public.events where event_id = change_request.event_id for update;
    if not found or planned.event_coordinator_id is distinct from auth.uid() then return jsonb_build_object('error', 'Change request not found or access unavailable.', 'status', 404); end if;
    if change_request.status <> 'pending_review' or change_request.importance <> 'important' then return jsonb_build_object('error', 'This change request no longer requires a decision.', 'status', 409); end if;
    if planned.status not in ('planning', 'pending_safety_checks', 'confirmed') then return jsonb_build_object('error', 'This event can no longer be changed.', 'status', 409); end if;

    if decision = 'approve' then
        if planned.updated_at is distinct from change_request.expected_event_updated_at then
            return jsonb_build_object('error', 'The event changed after this request was submitted. Reject this request and ask the organiser to submit an updated request.', 'stale', true, 'status', 409);
        end if;
        begin select * into candidate from jsonb_populate_record(planned, change_request.proposed_values);
        exception when others then return jsonb_build_object('error', 'The proposed values can no longer be applied.', 'status', 409); end;
        -- Keep the event write, decision, and required Critical Edit entry in
        -- one subtransaction. If an existing arrangement guard refuses the
        -- event write, none of the three is left half-applied and the caller
        -- receives the useful conflict instead of a generic service outage.
        begin
            perform set_config('connectsphere.change_request_workflow', 'true', true);
            perform set_config('connectsphere.change_request_importance', 'important', true);
            perform set_config('connectsphere.safety_workflow', 'true', true);
            update public.events set
                event_name = candidate.event_name, description = candidate.description,
                start_datetime = candidate.start_datetime, end_datetime = candidate.end_datetime,
                capacity_needed = candidate.capacity_needed, room_layout = candidate.room_layout,
                required_facilities = candidate.required_facilities,
                need_wheelchair_accessibility = candidate.need_wheelchair_accessibility,
                need_blind_accessibility = candidate.need_blind_accessibility,
                equipment_requirements = candidate.equipment_requirements
            where event_id = planned.event_id returning * into planned;
            update public.event_change_request set status = 'approved', reviewed_at = clock_timestamp(),
                reviewed_by = auth.uid(), decision_reason = decision_reason_value
            where event_change_request_id = p_request_id returning * into change_request;
            insert into public.event_activity (event_id, changed_by, change_type, changes, event_change_request_id)
            values (planned.event_id, auth.uid(), 'critical_edit', change_request.changes, change_request.event_change_request_id);
        exception
            when check_violation or foreign_key_violation or not_null_violation or insufficient_privilege then
                return jsonb_build_object('error', sqlerrm, 'status', 409);
            when others then
                return jsonb_build_object(
                    'error', 'The approved changes could not be applied. Refresh the request and try again.',
                    'status', 409
                );
        end;
    else
        update public.event_change_request set status = 'rejected', reviewed_at = clock_timestamp(),
            reviewed_by = auth.uid(), decision_reason = decision_reason_value
        where event_change_request_id = p_request_id returning * into change_request;
    end if;

    return jsonb_build_object(
        'message', case when decision = 'approve' then 'Change request approved and event information updated.' else 'Change request rejected. The event was not changed.' end,
        'change_request', to_jsonb(change_request), 'event', to_jsonb(planned)
    );
end;
$function$;

REVOKE ALL ON FUNCTION "public"."review_event_change_request"(bigint, text, text) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.review_venue_booking (
  p_booking_id uuid,
  p_outcome    text,
  p_comments   text
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    pending public.venue_booking_requests;
    decided public.venue_booking_requests;
    planned public.events;
    chosen public.venues;
    shortfalls text[];
    blocking jsonb;
    comments text := nullif(trim(coalesce(p_comments, '')), '');
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('venue_staff') then
        return jsonb_build_object('error', 'Only Venue Staff can approve or reject venue bookings.', 'status', 403);
    end if;
    if p_outcome is null or p_outcome not in ('approved', 'rejected') then
        return jsonb_build_object('error', 'Choose Approve or Reject.', 'status', 400);
    end if;
    if p_outcome = 'rejected' and comments is null then
        return jsonb_build_object(
            'error', 'Enter a reason for rejecting this request.',
            'errors', jsonb_build_object('comments', 'A reason is required when rejecting.'),
            'status', 400
        );
    end if;
    if comments is not null and length(comments) > 2000 then
        return jsonb_build_object('error', 'Comments must be 2000 characters or fewer.', 'status', 400);
    end if;

    select * into pending from public.venue_booking_requests where booking_id = p_booking_id;
    if not found then
        return jsonb_build_object('error', 'Booking request not found or access unavailable.', 'status', 404);
    end if;
    if pending.status <> 'submitted' then
        return jsonb_build_object(
            'error', 'This request has already been ' || pending.status || '.', 'status', 409
        );
    end if;

    if p_outcome = 'approved' then
        -- FOR SHARE: no edit to this venue can commit until this approval has,
        -- so the venue checked below is the venue booked.
        select * into chosen from public.venues where venue_id = pending.venue_id for share;
        if not found or chosen.deleted_at is not null then
            return jsonb_build_object(
                'error', 'This venue has been removed from the catalogue, so it can no longer be approved. Reject the request instead.',
                'status', 409
            );
        end if;

        if pending.event_id is not null then
            -- And the same for the event: a critical edit waits for this.
            select * into planned from public.events where event_id = pending.event_id for share;
            if found then
                if planned.status is distinct from 'planning'::public.event_status then
                    return jsonb_build_object(
                        'error', 'This event is ' || planned.status || ', so its venue can no longer be approved. Reject the request instead.',
                        'status', 409
                    );
                end if;
                if pending.starts_at is distinct from planned.start_datetime
                    or pending.ends_at is distinct from planned.end_datetime
                    or (planned.capacity_needed is not null
                        and pending.attendance is distinct from planned.capacity_needed) then
                    return jsonb_build_object(
                        'error', 'The event''s date, time or attendance has changed since this was requested, so approving it would book the wrong period. Reject it so the Event Coordinator can request again.',
                        'status', 409
                    );
                end if;
                shortfalls := public.venue_shortfalls_for_event(chosen, planned);
                if cardinality(shortfalls) > 0 then
                    return jsonb_build_object(
                        'error', 'The event has changed since this was requested, and the venue no longer meets its requirements. Reject the request instead.',
                        'unmet_requirements', to_jsonb(shortfalls),
                        'status', 409
                    );
                end if;
            end if;
        end if;

        blocking := public.venue_booking_conflicts(
            pending.venue_id, pending.starts_at, pending.ends_at, pending.booking_id, true
        );
        if jsonb_array_length(blocking) > 0 then
            return jsonb_build_object(
                'error', 'This venue is already booked for an overlapping period, so this request can only be rejected.',
                'conflicts', blocking,
                'status', 409
            );
        end if;
    end if;

    begin
        update public.venue_booking_requests
        set status = p_outcome,
            reviewed_by = auth.uid(),
            reviewed_at = now(),
            review_comments = comments
        where booking_id = p_booking_id and status = 'submitted'
        returning * into decided;
    exception when exclusion_violation then
        return jsonb_build_object(
            'error', 'Another booking for this venue at an overlapping time was approved just now, so this request can only be rejected.',
            'conflicts', public.venue_booking_conflicts(
                pending.venue_id, pending.starts_at, pending.ends_at, pending.booking_id, true
            ),
            'status', 409
        );
    end;

    if decided.booking_id is null then
        return jsonb_build_object('error', 'Another member of Venue Staff decided this request first.', 'status', 409);
    end if;



    return jsonb_build_object('booking', to_jsonb(decided));
end;
$function$;

REVOKE ALL ON FUNCTION "public"."review_venue_booking"(uuid, text, text) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.safety_review_event (
  p_event_id integer
)
  RETURNS jsonb
  LANGUAGE plpgsql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare event_row public.events; result jsonb;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_safety_officer_role() then
        return jsonb_build_object('error', 'Only Safety Officers can review operational safety arrangements.', 'status', 403);
    end if;
    select * into event_row from public.events
    where event_id = p_event_id and status = 'pending_safety_checks';
    if not found then return jsonb_build_object('error', 'Event not found or no longer awaiting safety checks.', 'status', 404); end if;

    select jsonb_build_object(
        'event_id', event_row.event_id,
        'event_name', event_row.event_name,
        'start_datetime', event_row.start_datetime,
        'end_datetime', event_row.end_datetime,
        'expected_attendance', event_row.capacity_needed,
        'venue_name', v.venue_name,
        'venue_capacity', v.capacity,
        'room_layout', replace(coalesce(event_row.room_layout::text, ''), '_', ' '),
        'emergency_access', v.emergency_access,
        'accessibility_requirements', to_jsonb(array_remove(array[
            case when event_row.need_wheelchair_accessibility then 'Wheelchair accessibility required' end,
            case when event_row.need_blind_accessibility then 'Blind-accessibility support required' end,
            case when v.wheelchair_accessible then 'Venue has wheelchair access' end,
            case when v.blind_accessible then 'Venue has blind-accessibility support' end
        ], null)),
        'equipment_placement', coalesce((
            select jsonb_agg(item order by item)
            from (
                select event_row.equipment_placement_plan as item
                where nullif(btrim(event_row.equipment_placement_plan), '') is not null
                union all
                select q.equipment_type || ' – ' || q.equipment_model || ' (quantity ' || r.quantity || ')'
                from public.equipment_reservations r join public.equipment q using (equipment_id)
                where r.event_id = event_row.event_id
            ) arranged_equipment
        ), '[]'::jsonb),
        'crowd_movement', event_row.crowd_movement_plan,
        'venue_restrictions', v.safety_restrictions
    ) into result
    from public.venue_booking_requests b
    join public.venues v using (venue_id)
    where b.event_id = event_row.event_id and b.status = 'approved'
    order by b.reviewed_at desc nulls last
    limit 1;
    return jsonb_build_object('event', coalesce(result, to_jsonb(event_row)));
end;
$function$;

REVOKE ALL ON FUNCTION "public"."safety_review_event"(integer) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.safety_review_queue()
  RETURNS jsonb
  LANGUAGE plpgsql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare result jsonb;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_safety_officer_role() then
        return jsonb_build_object('error', 'Only Safety Officers can review operational safety arrangements.', 'status', 403);
    end if;
    select coalesce(jsonb_agg(jsonb_build_object(
        'event_id', e.event_id,
        'event_name', e.event_name,
        'start_datetime', e.start_datetime,
        'end_datetime', e.end_datetime,
        'capacity_needed', e.capacity_needed,
        'venue_name', venue.venue_name
    ) order by e.start_datetime), '[]'::jsonb) into result
    from public.events e
    left join lateral (
        select v.venue_name
        from public.venue_booking_requests b join public.venues v using (venue_id)
        where b.event_id = e.event_id and b.status = 'approved'
        order by b.reviewed_at desc nulls last
        limit 1
    ) venue on true
    where e.status = 'pending_safety_checks' and e.safety_officer_id = auth.uid();
    return jsonb_build_object('events', result);
end;
$function$;

REVOKE ALL ON FUNCTION "public"."safety_review_queue"() FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.set_event_registration_period (
  p_event_id               integer,
  p_registration_opens_at  timestamp with time zone,
  p_registration_closes_at timestamp with time zone,
  p_waiting_list_enabled   boolean
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    declare saved public.events;
    begin
        if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
        select * into saved from public.events where event_id = p_event_id for update;
        if not found or saved.event_organiser_id is distinct from auth.uid()
            or not public.has_booking_role('event_organiser') then
            return jsonb_build_object('error', 'Only the assigned Event Organiser can manage registration.', 'status', 403);
        end if;
        if saved.status not in ('planning', 'pending_safety_checks', 'confirmed')
            or saved.end_datetime <= clock_timestamp()
            or saved.registration_closes_at <= clock_timestamp() then
            return jsonb_build_object('error', 'Registration settings can only change before or during registration.', 'status', 409);
        end if;
        if p_registration_opens_at is null or p_registration_closes_at is null
            or not isfinite(p_registration_opens_at) or not isfinite(p_registration_closes_at)
            or p_registration_closes_at <= p_registration_opens_at or p_waiting_list_enabled is null then
            return jsonb_build_object('error', 'Provide valid opening and closing times; closing must be after opening.', 'status', 400);
        end if;
        if saved.start_datetime is null or not isfinite(saved.start_datetime) then
            return jsonb_build_object('error', 'Set a valid event start time before configuring registration.', 'status', 400,
                'errors', jsonb_build_object('registration_opens_at', 'Set a valid event start time first.'));
        end if;
        if p_registration_opens_at >= saved.start_datetime then
            return jsonb_build_object('error', 'Registration must open before the event starts.', 'status', 400,
                'errors', jsonb_build_object('registration_opens_at', 'Registration must open before the event starts.'));
        end if;
        if p_registration_closes_at >= saved.start_datetime then
            return jsonb_build_object('error', 'Registration must close before the event starts.', 'status', 400,
                'errors', jsonb_build_object('registration_closes_at', 'Registration must close before the event starts.'));
        end if;
        update public.events set registration_opens_at = p_registration_opens_at,
            registration_closes_at = p_registration_closes_at,
            waiting_list_enabled = p_waiting_list_enabled
        where event_id = p_event_id returning * into saved;
        return jsonb_build_object('event', to_jsonb(saved));
    end;
    $function$;

REVOKE ALL ON FUNCTION "public"."set_event_registration_period"(integer, timestamp WITH time zone, timestamp WITH time zone, boolean) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.set_event_registration_ready (
  p_event_id integer,
  p_ready    boolean
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare saved public.events;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    select * into saved from public.events where event_id = p_event_id for update;
    if not found or saved.event_coordinator_id is distinct from auth.uid() then
        return jsonb_build_object('error', 'Only the assigned Event Coordinator can update registration readiness.', 'status', 403);
    end if;
    if saved.status not in ('planning', 'pending_safety_checks', 'confirmed') then
        return jsonb_build_object('error', 'Registration readiness cannot change at this stage.', 'status', 409);
    end if;
    if p_ready is null then return jsonb_build_object('error', 'Readiness must be true or false.', 'status', 400); end if;
    update public.events set registration_ready = p_ready where event_id = p_event_id returning * into saved;
    return jsonb_build_object('event', to_jsonb(saved), 'blockers', public.event_confirmation_blockers(saved));
end;
$function$;

REVOKE ALL ON FUNCTION "public"."set_event_registration_ready"(integer, boolean) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.set_updated_at()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  AS $function$
begin
  new.updated_at = now();
  return new;
end;
$function$;

CREATE OR REPLACE FUNCTION public.set_venue_booking_occupied()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
begin
    select new.starts_at - make_interval(mins => v.default_setup_minutes),
           new.ends_at + make_interval(mins => v.default_turnaround_minutes)
    into new.occupied_from, new.occupied_until
    from public.venues v where v.venue_id = new.venue_id;
    if tg_op = 'UPDATE' and (new.venue_id, new.starts_at, new.ends_at)
        is distinct from (old.venue_id, old.starts_at, old.ends_at) then
        new.hold_expires_at := null;
    end if;
    return new;
end;
$function$;

CREATE OR REPLACE FUNCTION public.submit_event_change_request (
  p_event_id                  integer,
  p_reason                    text,
  p_proposed_values           jsonb,
  p_expected_event_updated_at timestamp with time zone,
  p_confirm_critical          boolean                  DEFAULT false
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    planned public.events;
    candidate public.events;
    saved public.event_change_request;
    calculated_changes jsonb := '{}'::jsonb;
    changed_key text;
    readable_fields jsonb;
    is_important boolean;
    allowed_fields constant text[] := array[
        'event_name', 'description', 'start_datetime', 'end_datetime',
        'capacity_needed', 'room_layout', 'required_facilities',
        'need_wheelchair_accessibility', 'need_blind_accessibility',
        'equipment_requirements'
    ];
    important_fields constant text[] := array[
        'start_datetime', 'end_datetime', 'capacity_needed', 'room_layout',
        'required_facilities', 'need_wheelchair_accessibility',
        'need_blind_accessibility', 'equipment_requirements'
    ];
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    if not public.has_booking_role('event_organiser') then
        return jsonb_build_object('error', 'Only Event Organisers can submit event change requests.', 'status', 403);
    end if;
    if nullif(btrim(coalesce(p_reason, '')), '') is null then
        return jsonb_build_object('error', 'The change request could not be submitted because some details are invalid.',
            'errors', jsonb_build_object('reason', 'Please provide a reason for this change request'), 'status', 400);
    end if;
    if length(btrim(p_reason)) > 2000 then return jsonb_build_object('error', 'The reason must be 2000 characters or fewer.', 'status', 400); end if;
    if jsonb_typeof(p_proposed_values) is distinct from 'object' then return jsonb_build_object('error', 'Proposed changes must be a JSON object.', 'status', 400); end if;
    if exists (select 1 from jsonb_object_keys(p_proposed_values) key where not (key = any(allowed_fields))) then
        return jsonb_build_object('error', 'One or more proposed fields cannot be changed.', 'status', 400);
    end if;

    select * into planned from public.events where event_id = p_event_id for update;
    if not found or planned.event_organiser_id is distinct from auth.uid() then return jsonb_build_object('error', 'Event not found or access unavailable.', 'status', 404); end if;
    if planned.status not in ('planning', 'pending_safety_checks', 'confirmed') then return jsonb_build_object('error', 'This event can no longer accept change requests.', 'status', 409); end if;
    if planned.updated_at is distinct from p_expected_event_updated_at then return jsonb_build_object('error', 'This event changed while you were editing. Reload it and try again.', 'stale', true, 'status', 409); end if;
    if exists (select 1 from public.event_change_request where event_id = p_event_id and status = 'pending_review') then return jsonb_build_object('error', 'This event already has a change request pending review.', 'status', 409); end if;

    begin select * into candidate from jsonb_populate_record(planned, p_proposed_values);
    exception when others then return jsonb_build_object('error', 'One or more proposed values are invalid.', 'status', 400); end;
    for changed_key in select jsonb_object_keys(p_proposed_values) loop
        if (to_jsonb(candidate) -> changed_key) = 'null'::jsonb then return jsonb_build_object('error', 'Proposed values cannot be empty.', 'status', 400); end if;
        if (to_jsonb(candidate) -> changed_key) is distinct from (to_jsonb(planned) -> changed_key) then
            calculated_changes := calculated_changes || jsonb_build_object(changed_key,
                jsonb_build_object('from', to_jsonb(planned) -> changed_key, 'to', to_jsonb(candidate) -> changed_key));
        end if;
    end loop;
    if calculated_changes = '{}'::jsonb then return jsonb_build_object('error', 'Make at least one change before submitting.', 'status', 400); end if;
    if candidate.end_datetime <= candidate.start_datetime then return jsonb_build_object('error', 'The event must end after it starts.', 'status', 400); end if;
    if p_proposed_values ? 'start_datetime' and candidate.start_datetime <= now() then return jsonb_build_object('error', 'The event must start in the future.', 'status', 400); end if;
    if candidate.capacity_needed < 1 then return jsonb_build_object('error', 'Expected attendance must be at least 1.', 'status', 400); end if;

    is_important := calculated_changes ?| important_fields;
    if planned.status = 'confirmed' and is_important and not coalesce(p_confirm_critical, false) then
        select coalesce(jsonb_agg(case key
            when 'start_datetime' then 'Proposed start date and time' when 'end_datetime' then 'Proposed end date and time'
            when 'capacity_needed' then 'Expected attendance' when 'room_layout' then 'Room layout'
            when 'required_facilities' then 'Venue requirements' when 'need_wheelchair_accessibility' then 'Wheelchair accessibility'
            when 'need_blind_accessibility' then 'Accessibility for blind attendees' when 'equipment_requirements' then 'Equipment requirements'
            end order by key), '[]'::jsonb) into readable_fields
        from jsonb_object_keys(calculated_changes) key where key = any(important_fields);
        return jsonb_build_object('error', 'Review and confirm changes that may affect existing arrangements.', 'critical_fields', readable_fields, 'status', 409);
    end if;

    insert into public.event_change_request (
        event_id, requested_by, assigned_coordinator_id, reason, proposed_values,
        changes, expected_event_updated_at, importance, status, reviewed_at, reviewed_by
    ) values (
        planned.event_id, auth.uid(), planned.event_coordinator_id, btrim(p_reason),
        p_proposed_values, calculated_changes, planned.updated_at,
        case when is_important then 'important' else 'non_important' end,
        case when is_important
            then 'pending_review'::public.event_change_request_status
            else 'approved'::public.event_change_request_status
        end,
        case when is_important then null else clock_timestamp() end,
        case when is_important then null else auth.uid() end
    ) returning * into saved;

    if not is_important then
        perform set_config('connectsphere.change_request_workflow', 'true', true);
        perform set_config('connectsphere.change_request_importance', 'non_important', true);
        update public.events set event_name = candidate.event_name, description = candidate.description
        where event_id = planned.event_id returning * into planned;
        insert into public.event_activity (event_id, changed_by, change_type, changes, event_change_request_id)
        values (planned.event_id, auth.uid(), 'edit', calculated_changes, saved.event_change_request_id);
    end if;

    return jsonb_build_object(
        'message', case when is_important then 'Event change request submitted successfully.' else 'Non-critical changes were recorded and applied successfully.' end,
        'change_request', to_jsonb(saved)
    );
end;
$function$;

REVOKE ALL ON FUNCTION "public"."submit_event_change_request"(integer, text, jsonb, timestamp WITH time zone, boolean) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.submit_event_for_safety_checks (
  p_event_id integer
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare saved public.events; blockers text[]; coordinator text;
begin
    if auth.uid() is null then return jsonb_build_object('error', 'Please sign in again.', 'status', 401); end if;
    select * into saved from public.events where event_id = p_event_id for update;
    if not found or saved.event_coordinator_id is distinct from auth.uid() then
        return jsonb_build_object('error', 'Only the assigned Event Coordinator can submit this event for safety checks.', 'status', 403);
    end if;
    if saved.status <> 'planning' then
        return jsonb_build_object('error', 'Only events in Planning can be submitted for safety checks.', 'status', 409);
    end if;
    blockers := public.event_safety_check_blockers(saved);
    if cardinality(blockers) > 0 then
        return jsonb_build_object('error', 'Complete the planning arrangements first: ' || array_to_string(blockers, ' '),
                                  'blockers', to_jsonb(blockers), 'status', 409);
    end if;
    if saved.safety_officer_id is null then
        return jsonb_build_object('error', 'No Safety Officer is assigned to this event yet.', 'status', 409);
    end if;

    perform set_config('connectsphere.safety_submission', 'true', true);
    update public.events set status = 'pending_safety_checks' where event_id = p_event_id returning * into saved;
    perform set_config('connectsphere.safety_submission', '', true);

    coordinator := coalesce((select name from public.users where user_id = auth.uid()), 'the Event Coordinator');
    perform public.notify_user(saved.safety_officer_id, 'safety_check_requested', 'Event awaiting safety check',
        format('%s has been submitted for safety checks by %s.', coalesce(saved.event_name, 'An unnamed event'), coordinator),
        '/operational-safety-reviews/' || saved.event_id);
    return jsonb_build_object('event', to_jsonb(saved),
        'message', 'Event submitted for safety checks. The assigned Safety Officer has been notified.');
end;
$function$;

REVOKE ALL ON FUNCTION "public"."submit_event_for_safety_checks"(integer) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.submit_venue_booking (
  p_booking jsonb
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare
    saved public.venue_booking_requests;
    planned public.events;
    chosen public.venues;
    shortfalls text[];
    blocking jsonb;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('event_coordinator') then
        return jsonb_build_object('error', 'Only Event Coordinators can submit venue bookings.', 'status', 403);
    end if;
    if jsonb_typeof(p_booking) is distinct from 'object'
        or not (p_booking ?& array['venue_id','event_id','event_name','starts_at','ends_at','attendance','venue_requirements'])
        or jsonb_typeof(p_booking->'attendance') is distinct from 'number'
        or jsonb_typeof(p_booking->'event_id') is distinct from 'number'
        or jsonb_typeof(p_booking->'event_name') is distinct from 'string'
        or jsonb_typeof(p_booking->'venue_requirements') is distinct from 'string'
        or (p_booking->>'attendance') !~ '^[0-9]+$'
        or (p_booking->>'event_id') !~ '^[0-9]+$'
        or (p_booking->>'starts_at') !~ '(Z|[+-][0-9]{2}:[0-9]{2})$'
        or (p_booking->>'ends_at') !~ '(Z|[+-][0-9]{2}:[0-9]{2})$' then
        return jsonb_build_object('error', 'Provide all required booking details.', 'status', 400);
    end if;
    if (p_booking->>'starts_at')::timestamptz <= now() then
        return jsonb_build_object('error', 'Start must be in the future.', 'status', 400);
    end if;

    select * into planned from public.events
    where event_id = (p_booking->>'event_id')::integer;

    if not found or planned.event_coordinator_id is distinct from auth.uid() then
        return jsonb_build_object(
            'error', 'That event is not one you are planning.', 'status', 404
        );
    end if;
    if planned.status is distinct from 'planning'::public.event_status then
        return jsonb_build_object(
            'error', 'A venue can only be requested while the event is in planning.',
            'status', 409
        );
    end if;

    select * into chosen from public.venues
    where venue_id = (p_booking->>'venue_id')::uuid and deleted_at is null;

    if not found then
        return jsonb_build_object('error', 'Select an existing venue.', 'status', 400);
    end if;

    if (p_booking->>'starts_at')::timestamptz is distinct from planned.start_datetime
        or (p_booking->>'ends_at')::timestamptz is distinct from planned.end_datetime
        or (planned.capacity_needed is not null
            and (p_booking->>'attendance')::integer is distinct from planned.capacity_needed) then
        return jsonb_build_object(
            'error', 'These booking details no longer match the event. Reload the '
                     'event and try again.',
            'status', 409
        );
    end if;

    shortfalls := public.venue_shortfalls_for_event(chosen, planned);
    if cardinality(shortfalls) > 0 then
        return jsonb_build_object(
            'error', 'This venue does not meet the requirements recorded for this event.',
            'unmet_requirements', to_jsonb(shortfalls),
            'status', 409
        );
    end if;

    -- Only an approved booking makes the venue unavailable. Overlapping
    -- pending requests are allowed: none of them has the venue yet.
    blocking := public.venue_booking_conflicts(
        chosen.venue_id, planned.start_datetime, planned.end_datetime, null, true
    );
    if jsonb_array_length(blocking) > 0 then
        return jsonb_build_object(
            'error', 'This venue is already booked for part of this event''s time.',
            'conflicts', blocking,
            'status', 409
        );
    end if;

    insert into public.venue_booking_requests
        (venue_id, event_id, requested_by, event_name, starts_at, ends_at, attendance,
         venue_requirements)
    values ((p_booking->>'venue_id')::uuid, planned.event_id, auth.uid(),
        trim(p_booking->>'event_name'),
        (p_booking->>'starts_at')::timestamptz, (p_booking->>'ends_at')::timestamptz,
        (p_booking->>'attendance')::integer, trim(p_booking->>'venue_requirements'))
    returning * into saved;
    return to_jsonb(saved);
exception when invalid_text_representation or datetime_field_overflow or invalid_datetime_format
    or numeric_value_out_of_range or check_violation or not_null_violation or foreign_key_violation then
    return jsonb_build_object('error', 'Provide valid, complete booking details.', 'status', 400);
end;
$function$;

REVOKE ALL ON FUNCTION "public"."submit_venue_booking"(jsonb) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.track_venue_update()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  AS $function$
begin
    new.version := old.version + 1;
    new.updated_at := clock_timestamp();
    return new;
end;
$function$;

CREATE OR REPLACE FUNCTION public.unblock_venue (
  p_block_id uuid
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare removed public.venue_blocks;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('venue_staff') then
        return jsonb_build_object('error', 'Only Venue Staff can remove an unavailable period.', 'status', 403);
    end if;
    delete from public.venue_blocks where block_id = p_block_id returning * into removed;
    if not found then
        return jsonb_build_object('error', 'Unavailable period not found.', 'status', 404);
    end if;
    return jsonb_build_object('block', to_jsonb(removed));
end;
$function$;

REVOKE ALL ON FUNCTION "public"."unblock_venue"(uuid) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.update_equipment_reservation (
  p_reservation_id uuid,
  p_quantity       integer
)
  RETURNS jsonb
  LANGUAGE sql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    select public.change_equipment_reservation(p_reservation_id, p_quantity, false);
$function$;

REVOKE ALL ON FUNCTION "public"."update_equipment_reservation"(uuid, integer) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.venue_availability (
  p_venue_id uuid,
  p_starts   timestamp with time zone,
  p_ends     timestamp with time zone
)
  RETURNS jsonb
  LANGUAGE plpgsql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare period tstzrange;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not (public.has_booking_role('event_coordinator') or public.has_booking_role('venue_staff')) then
        return jsonb_build_object('error', 'Only Event Coordinators and Venue Staff can view venue availability.', 'status', 403);
    end if;
    if p_ends <= p_starts or p_ends - p_starts > interval '100 days' then
        return jsonb_build_object('error', 'Choose a period of up to 100 days.', 'status', 400);
    end if;
    if not exists (select 1 from public.venues where venue_id = p_venue_id and deleted_at is null) then
        return jsonb_build_object('error', 'Venue not found or access unavailable.', 'status', 404);
    end if;
    period := tstzrange(p_starts, p_ends, '[)');
    return jsonb_build_object(
        'bookings', coalesce((
            select jsonb_agg(public.venue_booking_summary(b) order by b.starts_at)
            from public.venue_booking_requests b
            where b.venue_id = p_venue_id and b.status in ('approved', 'submitted')
              and tstzrange(b.occupied_from, b.occupied_until, '[)') && period
        ), '[]'::jsonb),
        'blocks', coalesce((
            select jsonb_agg(jsonb_build_object('block_id', k.block_id, 'starts_at', k.starts_at,
                                                'ends_at', k.ends_at, 'reason', k.reason) order by k.starts_at)
            from public.venue_blocks k
            where k.venue_id = p_venue_id and tstzrange(k.starts_at, k.ends_at, '[)') && period
        ), '[]'::jsonb)
    );
end;
$function$;

REVOKE ALL ON FUNCTION "public"."venue_availability"(uuid, timestamp WITH time zone, timestamp WITH time zone) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.venue_block_summary (
  k public.venue_blocks
)
  RETURNS jsonb
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    select jsonb_build_object('block_id', k.block_id, 'venue_id', k.venue_id, 'status', 'blocked',
                              'starts_at', k.starts_at, 'ends_at', k.ends_at, 'reason', k.reason);
$function$;

REVOKE ALL ON FUNCTION "public"."venue_block_summary"(public.venue_blocks) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.venue_booking_conflicts (
  p_venue_id      uuid,
  p_starts        timestamp with time zone,
  p_ends          timestamp with time zone,
  p_exclude       uuid                     DEFAULT NULL::uuid,
  p_approved_only boolean                  DEFAULT false
)
  RETURNS jsonb
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    with wanted as (
        select tstzrange(p_starts - make_interval(mins => v.default_setup_minutes),
                         p_ends + make_interval(mins => v.default_turnaround_minutes), '[)') as period
        from public.venues v where v.venue_id = p_venue_id and auth.uid() is not null
    )
    select coalesce(jsonb_agg(item order by item->>'starts_at'), '[]'::jsonb) from (
        select public.venue_booking_summary(b) as item
        from public.venue_booking_requests b, wanted
        where b.venue_id = p_venue_id and b.booking_id is distinct from p_exclude
          and tstzrange(b.occupied_from, b.occupied_until, '[)') && wanted.period
          and (b.status = 'approved'
               or (b.status = 'submitted' and b.hold_expires_at > now())
               or (not p_approved_only and b.status = 'submitted'
                   and (public.has_booking_role('venue_staff') or b.requested_by = auth.uid())))
        union all
        select public.venue_block_summary(k)
        from public.venue_blocks k, wanted
        where k.venue_id = p_venue_id and tstzrange(k.starts_at, k.ends_at, '[)') && wanted.period
    ) found;
$function$;

REVOKE ALL ON FUNCTION "public"."venue_booking_conflicts"(uuid, timestamp WITH time zone, timestamp WITH time zone, uuid, boolean) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.venue_booking_summary (
  b public.venue_booking_requests
)
  RETURNS jsonb
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    select jsonb_build_object(
        'booking_id', b.booking_id, 'venue_id', b.venue_id,
        'status', case when b.status = 'submitted' and b.hold_expires_at > now() then 'held' else b.status end,
        'starts_at', b.starts_at, 'ends_at', b.ends_at, 'hold_expires_at', b.hold_expires_at,
        'occupied_from', b.occupied_from, 'occupied_until', b.occupied_until
    ) || case
        when public.has_booking_role('venue_staff') or b.requested_by = auth.uid()
        then jsonb_build_object('event_id', b.event_id, 'event_name', b.event_name, 'visible', true)
        else jsonb_build_object('visible', false)
    end;
$function$;

REVOKE ALL ON FUNCTION "public"."venue_booking_summary"(public.venue_booking_requests) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.venue_shortfalls_for_event (
  p_venue public.venues,
  p_event public.events
)
  RETURNS text[]
  LANGUAGE sql
  STABLE
  SET search_path TO 'public'
  AS $function$
    select coalesce(array_agg(shortfall), array[]::text[])
    from (
        select 'Holds ' || p_venue.capacity || ', but ' || p_event.capacity_needed
               || ' are expected.' as shortfall
        where p_event.capacity_needed is not null
          and p_venue.capacity < p_event.capacity_needed

        union all
        select 'Does not support a ' || replace(p_event.room_layout::text, '_', ' ')
               || ' layout.'
        where p_event.room_layout is not null
          and not (p_event.room_layout::text = any (p_venue.supported_room_layouts))

        union all
        select 'Missing ' || array_to_string(
                   array(
                       select replace(facility, '_', ' ')
                       from unnest(p_event.required_facilities::text[]) as facility
                       where not (facility = any (p_venue.facilities))
                       order by facility
                   ), ', ') || '.'
        where p_event.required_facilities is not null
          and not (p_event.required_facilities::text[] <@ p_venue.facilities)

        union all
        select 'This venue is not wheelchair accessible.'
        where p_event.need_wheelchair_accessibility
          and not p_venue.wheelchair_accessible

        union all
        select 'This venue is not accessible for blind attendees.'
        where p_event.need_blind_accessibility
          and not p_venue.blind_accessible

        -- The catalogue's weekly hours, checked against each Singapore-time day
        -- the event runs on. A day the catalogue does not describe counts as
        -- closed, because booking it would be guesswork.
        union all
        select 'Closed on ' || array_to_string(closed_days, ', ') || '.'
        from (
            select array(
                select distinct initcap(day_name)
                from (
                    select lower(to_char(day, 'FMDay')) as day_name
                    from generate_series(
                        (p_event.start_datetime at time zone 'Asia/Singapore')::date,
                        (p_event.end_datetime at time zone 'Asia/Singapore')::date,
                        interval '1 day'
                    ) as day
                ) as days
                where not (p_venue.operating_hours ? day_name)
                   or coalesce(
                        (p_venue.operating_hours -> day_name ->> 'closed')::boolean,
                        false
                      )
                order by 1
            ) as closed_days
        ) as hours
        where cardinality(closed_days) > 0
    ) as shortfalls;
$function$;

REVOKE ALL ON FUNCTION "public"."venue_shortfalls_for_event"(public.venues, public.events) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.venue_unavailability (
  p_starts timestamp with time zone,
  p_ends   timestamp with time zone
)
  RETURNS jsonb
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    select coalesce(jsonb_agg(item order by item->>'starts_at'), '[]'::jsonb) from (
        select public.venue_booking_summary(b) as item
        from public.venue_booking_requests b join public.venues v on v.venue_id = b.venue_id
        where (b.status = 'approved' or (b.status = 'submitted' and b.hold_expires_at > now()))
          and tstzrange(b.occupied_from, b.occupied_until, '[)')
           && tstzrange(p_starts - make_interval(mins => v.default_setup_minutes),
                        p_ends + make_interval(mins => v.default_turnaround_minutes), '[)')
        union all
        select public.venue_block_summary(k)
        from public.venue_blocks k join public.venues v on v.venue_id = k.venue_id
        where tstzrange(k.starts_at, k.ends_at, '[)')
           && tstzrange(p_starts - make_interval(mins => v.default_setup_minutes),
                        p_ends + make_interval(mins => v.default_turnaround_minutes), '[)')
    ) found
    where auth.uid() is not null;
$function$;

REVOKE ALL ON FUNCTION "public"."venue_unavailability"(timestamp WITH time zone, timestamp WITH time zone) FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.visible_venue_bookings()
  RETURNS SETOF jsonb
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
    select to_jsonb(b) || jsonb_build_object(
        'venue_name', v.venue_name,
        'event_status', e.status,
        'requested_by_name', requester.name,
        'reviewed_by_name', reviewer.name,
        'current_shortfalls', case
            when b.status = 'submitted' and e.event_id is not null
            then to_jsonb(public.venue_shortfalls_for_event(v, e))
        end,
        'conflicts', case
            when b.status in ('submitted', 'approved')
            then public.venue_booking_conflicts(b.venue_id, b.starts_at, b.ends_at, b.booking_id)
            else '[]'::jsonb
        end
    )
    from public.venue_booking_requests b
    join public.venues v on v.venue_id = b.venue_id
    left join public.events e on e.event_id = b.event_id
    left join public.users requester on requester.user_id = b.requested_by
    left join public.users reviewer on reviewer.user_id = b.reviewed_by
    where auth.uid() is not null
      and (public.has_booking_role('venue_staff') or b.requested_by = auth.uid())
    order by b.submitted_at desc;
$function$;

REVOKE ALL ON FUNCTION "public"."visible_venue_bookings"() FROM PUBLIC, "anon";

CREATE OR REPLACE FUNCTION public.withdraw_event_registration (
  p_event_id integer
)
  RETURNS jsonb
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
  AS $function$
declare planned public.events; saved public.event_registration; instant timestamptz;
begin
    if auth.uid() is null then
        return jsonb_build_object('error', 'Please sign in again.', 'status', 401);
    end if;
    if not public.has_booking_role('attendee') then
        return jsonb_build_object('error', 'Only attendees can withdraw registrations.', 'status', 403);
    end if;
    -- Use the registration lock, then read the clock: waiting across event start
    -- must not allow a withdrawal that is now too late.
    select * into planned from public.events where event_id = p_event_id for update;
    instant := clock_timestamp();
    if not found then
        return jsonb_build_object('error', 'Registration not found.', 'status', 404);
    end if;
    select * into saved from public.event_registration
        where event_id = p_event_id and attendee_id = auth.uid();
    if not found then
        return jsonb_build_object('error', 'Registration not found.', 'status', 404);
    end if;
    if planned.start_datetime is null or instant >= planned.start_datetime then
        return jsonb_build_object('error', 'Registration cannot be withdrawn at or after the event start time.', 'status', 409);
    end if;
    if saved.status <> 'withdrawn' then
        update public.event_registration set status = 'withdrawn', withdrawn_at = instant
            where event_id = p_event_id and attendee_id = auth.uid() returning * into saved;
        -- Do not send a pending attendance confirmation after withdrawal.
        delete from public.registration_email_outbox
            where event_id = p_event_id and attendee_id = auth.uid() and sent_at is null;
    end if;
    return jsonb_build_object('message', 'Your registration has been successfully withdrawn.',
        'registration', to_jsonb(saved),
        'available_capacity', greatest(0, planned.capacity_needed - (select count(*)
            from public.event_registration where event_id = p_event_id and status = 'registered')));
end;
$function$;

REVOKE ALL ON FUNCTION "public"."withdraw_event_registration"(integer) FROM PUBLIC, "anon";

ALTER TABLE "public"."equipment_request"
  ADD CONSTRAINT "equipment_request_equipment_id_fkey" FOREIGN KEY (equipment_id) REFERENCES public.equipment(equipment_id);

ALTER TABLE "public"."equipment_reservations"
  ADD CONSTRAINT "equipment_reservations_created_by_fkey" FOREIGN KEY (created_by) REFERENCES auth.users(id);

ALTER TABLE "public"."equipment_reservations"
  ADD CONSTRAINT "equipment_reservations_equipment_id_fkey" FOREIGN KEY (equipment_id) REFERENCES public.equipment(equipment_id);

ALTER TABLE "public"."equipment_reservations"
  ADD CONSTRAINT "equipment_reservations_equipment_request_id_fkey" FOREIGN KEY (equipment_request_id) REFERENCES public.equipment_request(equipment_request_id);

ALTER TABLE "public"."event_change_request"
  ADD CONSTRAINT "event_change_request_decision_reason_check" CHECK (((status <> 'rejected'::public.event_change_request_status) OR (NULLIF(btrim(decision_reason), ''::text) IS
    NOT NULL)));

ALTER TABLE "public"."event_change_request"
  ADD CONSTRAINT "event_change_request_importance_check" CHECK ((importance = ANY (ARRAY['important'::text, 'non_important'::text])));

ALTER TABLE "public"."event_activity"
  ADD CONSTRAINT "event_activity_event_change_request_id_fkey" FOREIGN KEY (event_change_request_id) REFERENCES public.event_change_request(event_change_request_id) ON DELETE
    SET NULL;

ALTER TABLE "public"."event_change_request"
  ADD CONSTRAINT "event_change_request_review_state"
    CHECK
    ((((status = 'pending_review'::public.event_change_request_status) AND (reviewed_at IS NULL) AND (reviewed_by IS NULL)) OR ((status = ANY
    (ARRAY['approved'::public.event_change_request_status, 'rejected'::public.event_change_request_status])) AND (reviewed_at IS NOT NULL) AND (reviewed_by IS NOT NULL))));

ALTER TABLE "public"."event_registration"
  ADD CONSTRAINT "event_registration_attendee_id_fkey" FOREIGN KEY (attendee_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE "public"."event_request"
  ADD CONSTRAINT "complete_before_submit" CHECK (((status = ANY (ARRAY['draft'::public.event_status, 'cancelled'::public.event_status])) OR ((event_name IS
    NOT NULL) AND (purpose IS NOT NULL) AND (start_datetime IS NOT NULL) AND (end_datetime IS NOT NULL) AND (capacity_needed IS NOT NULL))));

ALTER TABLE "public"."event_request"
  ADD CONSTRAINT "event_request_equipment_requirements_is_array" CHECK ((jsonb_typeof(equipment_requirements) = 'array'::text));

ALTER TABLE "public"."event_request_amendment"
  ADD CONSTRAINT "event_request_amendment_event_request_id_fkey" FOREIGN KEY (event_request_id) REFERENCES public.event_request(event_request_id) ON DELETE CASCADE;

ALTER TABLE "public"."event_request_review"
  ADD CONSTRAINT "event_request_review_event_request_id_fkey" FOREIGN KEY (event_request_id) REFERENCES public.event_request(event_request_id) ON DELETE CASCADE;

ALTER TABLE "public"."event_request_review"
  ADD CONSTRAINT "event_request_review_reason_required" CHECK (((outcome = 'approved'::public.review_outcome) OR ((comments IS NOT NULL) AND (btrim(comments) <> ''::text))));

ALTER TABLE "public"."events"
  ADD CONSTRAINT "event_registration_period_check" CHECK ((((registration_opens_at IS NULL) AND (registration_closes_at IS NULL)) OR ((registration_opens_at IS
    NOT NULL) AND (registration_closes_at IS
    NOT NULL) AND isfinite(registration_opens_at) AND isfinite(registration_closes_at) AND (registration_closes_at > registration_opens_at))));

ALTER TABLE "public"."events"
  ADD CONSTRAINT "events_equipment_requirements_check" CHECK ((jsonb_typeof(equipment_requirements) = 'array'::text));

ALTER TABLE "public"."events"
  ADD CONSTRAINT "events_event_request_id_fkey" FOREIGN KEY (event_request_id) REFERENCES public.event_request(event_request_id);

ALTER TABLE "public"."equipment_request"
  ADD CONSTRAINT "equipment_request_event_id_fkey" FOREIGN KEY (event_id) REFERENCES public.events(event_id);

ALTER TABLE "public"."equipment_reservations"
  ADD CONSTRAINT "equipment_reservations_event_fkey" FOREIGN KEY (event_id) REFERENCES public.events(event_id);

ALTER TABLE "public"."event_activity"
  ADD CONSTRAINT "event_activity_event_id_fkey" FOREIGN KEY (event_id) REFERENCES public.events(event_id) ON DELETE CASCADE;

ALTER TABLE "public"."event_change_request"
  ADD CONSTRAINT "event_change_request_event_id_fkey" FOREIGN KEY (event_id) REFERENCES public.events(event_id) ON DELETE CASCADE;

ALTER TABLE "public"."event_registration"
  ADD CONSTRAINT "event_registration_event_id_fkey" FOREIGN KEY (event_id) REFERENCES public.events(event_id) ON DELETE CASCADE;

ALTER TABLE "public"."events"
  ADD CONSTRAINT "registration_before_event_start" CHECK (((registration_opens_at IS NULL) OR ((start_datetime IS
    NOT NULL) AND isfinite(start_datetime) AND (registration_closes_at < start_datetime))));

ALTER TABLE "public"."notifications"
  ADD CONSTRAINT "notifications_recipient_id_fkey" FOREIGN KEY (recipient_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE "public"."operational_safety_decision"
  ADD CONSTRAINT "operational_safety_decision_event_id_fkey" FOREIGN KEY (event_id) REFERENCES public.events(event_id) ON DELETE CASCADE;

ALTER TABLE "public"."registration_email_outbox"
  ADD CONSTRAINT "registration_email_outbox_event_id_attendee_id_fkey" FOREIGN KEY (event_id, attendee_id) REFERENCES public.event_registration(event_id, attendee_id)
    ON DELETE CASCADE;

ALTER TABLE "public"."user_roles"
  ADD CONSTRAINT "user_roles_role_id_fkey" FOREIGN KEY (role_id) REFERENCES public.roles(role_id) ON DELETE CASCADE;

ALTER TABLE "public"."equipment_request"
  ADD CONSTRAINT "equipment_request_requested_by_fkey" FOREIGN KEY (requested_by) REFERENCES public.users(user_id);

ALTER TABLE "public"."equipment_request"
  ADD CONSTRAINT "equipment_request_reviewed_by_fkey" FOREIGN KEY (reviewed_by) REFERENCES public.users(user_id);

ALTER TABLE "public"."event_change_request"
  ADD CONSTRAINT "event_change_request_assigned_coordinator_id_fkey" FOREIGN KEY (assigned_coordinator_id) REFERENCES public.users(user_id);

ALTER TABLE "public"."event_change_request"
  ADD CONSTRAINT "event_change_request_requested_by_fkey" FOREIGN KEY (requested_by) REFERENCES public.users(user_id);

ALTER TABLE "public"."event_change_request"
  ADD CONSTRAINT "event_change_request_reviewed_by_fkey" FOREIGN KEY (reviewed_by) REFERENCES public.users(user_id);

ALTER TABLE "public"."event_request"
  ADD CONSTRAINT "event_request_event_coordinator_id_fkey" FOREIGN KEY (event_coordinator_id) REFERENCES public.users(user_id);

ALTER TABLE "public"."event_request"
  ADD CONSTRAINT "event_request_event_organiser_id_fkey" FOREIGN KEY (event_organiser_id) REFERENCES public.users(user_id) ON DELETE CASCADE;

ALTER TABLE "public"."event_request_amendment"
  ADD CONSTRAINT "event_request_amendment_amended_by_fkey" FOREIGN KEY (amended_by) REFERENCES public.users(user_id);

ALTER TABLE "public"."event_request_review"
  ADD CONSTRAINT "event_request_review_reviewer_id_fkey" FOREIGN KEY (reviewer_id) REFERENCES public.users(user_id);

ALTER TABLE "public"."events"
  ADD CONSTRAINT "events_event_coordinator_id_fkey" FOREIGN KEY (event_coordinator_id) REFERENCES public.users(user_id);

ALTER TABLE "public"."events"
  ADD CONSTRAINT "events_event_organiser_id_fkey" FOREIGN KEY (event_organiser_id) REFERENCES public.users(user_id);

ALTER TABLE "public"."events"
  ADD CONSTRAINT "events_safety_officer_id_fkey" FOREIGN KEY (safety_officer_id) REFERENCES public.users(user_id);

ALTER TABLE "public"."events"
  ADD CONSTRAINT "events_technical_support_id_fkey" FOREIGN KEY (technical_support_id) REFERENCES public.users(user_id);

ALTER TABLE "public"."events"
  ADD CONSTRAINT "events_venue_staff_id_fkey" FOREIGN KEY (venue_staff_id) REFERENCES public.users(user_id);

ALTER TABLE "public"."operational_safety_decision"
  ADD CONSTRAINT "operational_safety_decision_safety_officer_id_fkey" FOREIGN KEY (safety_officer_id) REFERENCES public.users(user_id);

ALTER TABLE "public"."user_roles"
  ADD CONSTRAINT "user_roles_user_id_fkey" FOREIGN KEY (user_id) REFERENCES public.users(user_id) ON DELETE CASCADE;

ALTER TABLE "public"."users"
  ADD CONSTRAINT "users_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE "public"."venue_blocks"
  ADD CONSTRAINT "venue_blocks_created_by_fkey" FOREIGN KEY (created_by) REFERENCES auth.users(id);

ALTER TABLE "public"."venue_booking_requests"
  ADD CONSTRAINT "venue_booking_no_double_booking" EXCLUDE USING gist (venue_id WITH =, tstzrange(occupied_from, occupied_until, '[)'::text) WITH &&)
    WHERE ((status = 'approved'::text));

ALTER TABLE "public"."venue_booking_requests"
  ADD CONSTRAINT "venue_booking_requests_event_id_fkey" FOREIGN KEY (event_id) REFERENCES public.events(event_id);

ALTER TABLE "public"."venue_booking_requests"
  ADD CONSTRAINT "venue_booking_requests_requested_by_fkey" FOREIGN KEY (requested_by) REFERENCES auth.users(id);

ALTER TABLE "public"."venue_booking_requests"
  ADD CONSTRAINT "venue_booking_requests_reviewed_by_fkey" FOREIGN KEY (reviewed_by) REFERENCES auth.users(id);

ALTER TABLE "public"."events"
  ADD CONSTRAINT "events_venue_id_fkey" FOREIGN KEY (venue_id) REFERENCES public.venues(venue_id) ON DELETE RESTRICT;

ALTER TABLE "public"."venue_blocks"
  ADD CONSTRAINT "venue_blocks_venue_id_fkey" FOREIGN KEY (venue_id) REFERENCES public.venues(venue_id);

ALTER TABLE "public"."venue_booking_requests"
  ADD CONSTRAINT "venue_booking_requests_venue_id_fkey" FOREIGN KEY (venue_id) REFERENCES public.venues(venue_id);

CREATE INDEX equipment_reservation_lookup ON public.equipment_reservations USING btree (equipment_id, starts_at, ends_at);

CREATE UNIQUE INDEX equipment_reservations_standalone_event_equipment ON public.equipment_reservations USING btree (event_id, equipment_id)
  WHERE (equipment_request_id IS NULL);

CREATE INDEX event_activity_event_idx ON public.event_activity USING btree (event_id, created_at DESC);

CREATE INDEX event_change_request_event_idx ON public.event_change_request USING btree (event_id, submitted_at DESC);

CREATE UNIQUE INDEX event_change_request_one_pending_idx ON public.event_change_request USING btree (event_id)
  WHERE (status = 'pending_review'::public.event_change_request_status);

CREATE INDEX event_request_amendment_request_idx ON public.event_request_amendment USING btree (event_request_id, created_at DESC);

CREATE INDEX event_request_review_request_idx ON public.event_request_review USING btree (event_request_id, created_at DESC);

CREATE INDEX events_venue_start_datetime_idx ON public.events USING btree (venue_id, start_datetime);

CREATE INDEX notifications_recipient_idx ON public.notifications USING btree (recipient_id, created_at DESC);

CREATE INDEX operational_safety_decision_event_idx ON public.operational_safety_decision USING btree (event_id, created_at DESC);

CREATE INDEX venue_booking_event_idx ON public.venue_booking_requests USING btree (event_id);

CREATE UNIQUE INDEX venue_booking_one_active_per_event_venue ON public.venue_booking_requests USING btree (event_id, venue_id)
  WHERE (status = ANY (ARRAY['submitted'::text, 'approved'::text]));

CREATE INDEX venue_booking_status_idx ON public.venue_booking_requests USING btree (status, submitted_at);

CREATE INDEX venue_booking_submitter_idx ON public.venue_booking_requests USING btree (requested_by, submitted_at DESC);

CREATE INDEX venues_active_catalogue_idx ON public.venues USING btree (venue_name)
  WHERE (deleted_at IS NULL);

CREATE UNIQUE INDEX venues_normalized_name_address_key ON public.venues
  USING btree
  (lower(btrim(venue_name)), lower(btrim(block_number)), lower(btrim(street_name)), postal_code, lower(btrim(COALESCE(building_name, ''::text))), lower(btrim(COALESCE(unit_number,
  ''::text))));

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_auth_user();

CREATE TRIGGER guard_equipment_request_acceptance
  BEFORE INSERT OR UPDATE ON public.equipment_request
  FOR EACH ROW
  EXECUTE FUNCTION public.guard_equipment_request_acceptance();

CREATE TRIGGER guard_equipment_request_review
  BEFORE INSERT OR DELETE OR UPDATE ON public.equipment_request
  FOR EACH ROW
  EXECUTE FUNCTION public.guard_equipment_request_review();

CREATE TRIGGER requests_update_event_status
  AFTER INSERT OR DELETE OR UPDATE ON public.equipment_request
  FOR EACH ROW
  EXECUTE FUNCTION public.refresh_arranged_event();

CREATE TRIGGER reservations_update_event_status
  AFTER INSERT OR DELETE OR UPDATE ON public.equipment_reservations
  FOR EACH ROW
  EXECUTE FUNCTION public.refresh_arranged_event();

CREATE TRIGGER create_event_after_request_approval
  AFTER UPDATE OF status ON public.event_request
  FOR EACH ROW
  WHEN (((new.status = 'planning'::public.event_status) AND (old.status IS DISTINCT FROM 'planning'::public.event_status)))
  EXECUTE FUNCTION public.create_event_from_approved_request();

CREATE TRIGGER event_request_updated_at
  BEFORE UPDATE ON public.event_request
  FOR EACH ROW
  EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER guard_request_lifecycle
  BEFORE INSERT OR UPDATE OF status ON public.event_request
  FOR EACH ROW
  EXECUTE FUNCTION public.guard_request_lifecycle();

CREATE TRIGGER notify_coordinator_assignment
  AFTER UPDATE OF event_coordinator_id ON public.event_request
  FOR EACH ROW
  EXECUTE FUNCTION public.notify_coordinator_assignment();

CREATE TRIGGER notify_event_request_submitted
  AFTER INSERT OR UPDATE OF status ON public.event_request
  FOR EACH ROW
  EXECUTE FUNCTION public.notify_event_request_submitted();

CREATE TRIGGER auto_assign_event_staff
  BEFORE INSERT ON public.events
  FOR EACH ROW
  EXECUTE FUNCTION public.auto_assign_event_staff();

CREATE TRIGGER guard_equipment_event
  BEFORE DELETE OR UPDATE ON public.events
  FOR EACH ROW
  EXECUTE FUNCTION public.guard_equipment_event();

CREATE TRIGGER guard_event_lifecycle
  BEFORE INSERT OR UPDATE ON public.events
  FOR EACH ROW
  EXECUTE FUNCTION public.guard_event_lifecycle();

CREATE TRIGGER guard_registration_settings
  BEFORE UPDATE ON public.events
  FOR EACH ROW
  EXECUTE FUNCTION public.guard_registration_settings();

CREATE TRIGGER guard_reviewed_equipment_event
  BEFORE UPDATE ON public.events
  FOR EACH ROW
  EXECUTE FUNCTION public.guard_reviewed_equipment_event();

CREATE TRIGGER notify_event_staff_assigned
  AFTER INSERT ON public.events
  FOR EACH ROW
  EXECUTE FUNCTION public.notify_event_staff_assigned();

CREATE TRIGGER record_event_status_change
  AFTER UPDATE ON public.events
  FOR EACH ROW
  WHEN ((old.status IS DISTINCT FROM new.status))
  EXECUTE FUNCTION public.record_event_status_change();

CREATE TRIGGER notify_venue_booking_change
  AFTER INSERT OR UPDATE OF status, hold_expires_at ON public.venue_booking_requests
  FOR EACH ROW
  EXECUTE FUNCTION public.notify_venue_booking_change();

CREATE TRIGGER venue_booking_occupied
  BEFORE INSERT OR UPDATE ON public.venue_booking_requests
  FOR EACH ROW
  EXECUTE FUNCTION public.set_venue_booking_occupied();

CREATE TRIGGER venue_updates_event_status
  AFTER INSERT OR DELETE OR UPDATE ON public.venue_booking_requests
  FOR EACH ROW
  EXECUTE FUNCTION public.refresh_arranged_event();

CREATE TRIGGER venue_changes_update_event_status
  AFTER UPDATE ON public.venues
  FOR EACH ROW
  EXECUTE FUNCTION public.refresh_venue_event_statuses();

CREATE TRIGGER venues_track_update
  BEFORE UPDATE ON public.venues
  FOR EACH ROW
  EXECUTE FUNCTION public.track_venue_update();

CREATE POLICY "authenticated_read_equipment" ON "public"."equipment"
  FOR SELECT
  TO "authenticated"
  USING (true);

CREATE POLICY "Users can delete their own requests" ON "public"."equipment_request"
  FOR DELETE
  TO "authenticated"
  USING ((auth.uid() = requested_by));

CREATE POLICY "authenticated_create_equipment_requests" ON "public"."equipment_request"
  FOR INSERT
  TO "authenticated"
  WITH CHECK (true);

CREATE POLICY "authenticated_read_equipment_requests" ON "public"."equipment_request"
  FOR SELECT
  TO "authenticated"
  USING (true);

CREATE POLICY "public_delete_equipment_requests" ON "public"."equipment_request"
  FOR DELETE
  TO PUBLIC
  USING (true);

CREATE POLICY "authenticated_read_event_activity" ON "public"."event_activity"
  FOR SELECT
  TO "authenticated"
  USING ((EXISTS ( SELECT 1
   FROM public.events e
  WHERE (e.event_id = event_activity.event_id))));

CREATE POLICY "authenticated_write_event_activity" ON "public"."event_activity"
  FOR INSERT
  TO "authenticated"
  WITH CHECK (((changed_by = ( SELECT auth.uid() AS uid)) AND (EXISTS ( SELECT 1
   FROM public.events e
  WHERE (e.event_id = event_activity.event_id)))));

CREATE POLICY "event_change_request_read_participants" ON "public"."event_change_request"
  FOR SELECT
  TO "authenticated"
  USING (((requested_by = ( SELECT auth.uid() AS uid)) OR (EXISTS ( SELECT 1
   FROM public.events e
  WHERE ((e.event_id = event_change_request.event_id) AND (e.event_coordinator_id = ( SELECT auth.uid() AS uid)))))));

CREATE POLICY "own_registration" ON "public"."event_registration"
  FOR SELECT
  TO "authenticated"
  USING ((attendee_id = ( SELECT auth.uid() AS uid)));

CREATE POLICY "authenticated_create_event_requests" ON "public"."event_request"
  FOR INSERT
  TO "authenticated"
  WITH CHECK ((event_organiser_id = ( SELECT auth.uid() AS uid)));

CREATE POLICY "authenticated_delete_draft_event_requests" ON "public"."event_request"
  FOR DELETE
  TO "authenticated"
  USING (((event_organiser_id = ( SELECT auth.uid() AS uid)) AND (status = 'draft'::public.event_status)));

CREATE POLICY "authenticated_read_event_requests" ON "public"."event_request"
  FOR SELECT
  TO "authenticated"
  USING (((event_organiser_id = ( SELECT auth.uid() AS uid)) OR (event_coordinator_id = ( SELECT auth.uid() AS uid))));

CREATE POLICY "authenticated_update_event_requests" ON "public"."event_request"
  FOR UPDATE
  TO "authenticated"
  USING (((event_organiser_id = ( SELECT auth.uid() AS uid)) OR (event_coordinator_id = ( SELECT auth.uid() AS uid))))
  WITH CHECK (((event_organiser_id = ( SELECT auth.uid() AS uid)) OR (event_coordinator_id = ( SELECT auth.uid() AS uid))));

CREATE POLICY "authenticated_create_amendments" ON "public"."event_request_amendment"
  FOR INSERT
  TO "authenticated"
  WITH CHECK (true);

CREATE POLICY "authenticated_read_amendments" ON "public"."event_request_amendment"
  FOR SELECT
  TO "authenticated"
  USING (true);

CREATE POLICY "authenticated_create_reviews" ON "public"."event_request_review"
  FOR INSERT
  TO "authenticated"
  WITH CHECK (true);

CREATE POLICY "authenticated_read_reviews" ON "public"."event_request_review"
  FOR SELECT
  TO "authenticated"
  USING (true);

CREATE POLICY "authenticated_read_events" ON "public"."events"
  FOR SELECT
  TO "authenticated"
  USING
    (((event_organiser_id = ( SELECT auth.uid() AS uid)) OR (event_coordinator_id = ( SELECT auth.uid() AS uid)) OR (technical_support_id = ( SELECT auth.uid() AS uid)) OR
    (venue_staff_id = ( SELECT auth.uid() AS uid)) OR (safety_officer_id = ( SELECT auth.uid() AS uid))));

CREATE POLICY "authenticated_update_events" ON "public"."events"
  FOR UPDATE
  TO "authenticated"
  USING (((event_coordinator_id = ( SELECT auth.uid() AS uid)) OR (technical_support_id = ( SELECT auth.uid() AS uid)) OR (venue_staff_id = ( SELECT auth.uid() AS uid))))
  WITH CHECK (((event_organiser_id IS NOT NULL) AND (event_coordinator_id IS NOT NULL)));

CREATE POLICY "authenticated_read_roles" ON "public"."roles"
  FOR SELECT
  TO PUBLIC
  USING ((auth.role() = 'authenticated'::text));

CREATE POLICY "authenticated_read_user_roles" ON "public"."user_roles"
  FOR SELECT
  TO PUBLIC
  USING ((auth.role() = 'authenticated'::text));

CREATE POLICY "authenticated_read_users" ON "public"."users"
  FOR SELECT
  TO "authenticated"
  USING (true);

CREATE POLICY "booking_read" ON "public"."venue_booking_requests"
  FOR SELECT
  TO "authenticated"
  USING (((requested_by = auth.uid()) OR public.has_booking_role('venue_staff'::text)));

CREATE POLICY "authenticated_manage_venues" ON "public"."venues"
  FOR ALL
  TO "authenticated"
  USING (true)
  WITH CHECK (true);

COMMENT ON COLUMN "public"."event_request"."equipment_requirements" IS 'Equipment the Event Organiser expects to need, as a JSON array of {equipment_type, quantity, notes} objects. Empty array means none.';

COMMENT ON COLUMN "public"."event_request"."registration_needs" IS 'Free-text description of the event''s attendee registration needs. Null means registration is not required.';

COMMENT ON COLUMN "public"."event_request"."status" IS 'Approval phase of the event lifecycle. A request leaves this table''s care at ''planning'' (approved, an events row now exists) or ''rejected'' (returned to the Organiser to amend and resubmit).';

COMMENT ON COLUMN "public"."events"."safety_officer_id" IS 'The Safety Officer assigned to the event, chosen at random on approval.';

COMMENT ON COLUMN "public"."events"."status" IS 'Operational phase of the event lifecycle. ''planning'' while arrangements are being made, ''pending_safety_checks'' while required safety checks remain, ''confirmed'' once arrangements are settled, and ''completed'' once the event is over. ''cancelled'' is reachable from any stage.';

COMMENT ON COLUMN "public"."venue_booking_requests"."event_id" IS 'The event in planning this venue is being requested for. Null only for requests taken before the planning-first flow existed.';

COMMENT ON EXTENSION "btree_gist" IS 'support for indexing common datatypes in GiST';

COMMENT ON EXTENSION "pg_cron" IS 'Job scheduler for PostgreSQL';

COMMENT ON POLICY "authenticated_delete_draft_event_requests" ON "public"."event_request" IS 'An Organiser may delete their own request only while it is a draft.';

COMMENT ON TABLE "public"."event_activity" IS 'Append-only record of changes made to an event during planning. change_type ''critical_edit'' marks a change the user was warned about and confirmed.';

COMMENT ON TABLE "public"."event_request_review" IS 'Audit trail of Event Coordinator decisions on event requests. Append only.';

COMMENT ON TABLE "public"."venues" IS 'Catalogue of ConnectSphere event spaces and their operational characteristics.';

GRANT EXECUTE ON FUNCTION "public"."assign_event_coordinator"() TO PUBLIC, "anon", "authenticated";

REVOKE ALL ON FUNCTION "public"."assign_event_coordinator"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."assign_event_coordinator"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."assign_event_coordinator"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."assign_event_request_coordinator"(bigint, uuid) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."assign_event_request_coordinator"(bigint, uuid) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."assign_event_request_coordinator"(bigint, uuid) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."assign_event_request_coordinator"(bigint, uuid) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."attendee_registration_events"() TO "authenticated";

REVOKE ALL ON FUNCTION "public"."attendee_registration_events"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."attendee_registration_events"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."attendee_registration_events"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."auto_assign_event_staff"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."auto_assign_event_staff"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."auto_assign_event_staff"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."block_venue"(uuid, timestamp WITH time zone, timestamp WITH time zone, text) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."block_venue"(uuid, timestamp WITH time zone, timestamp WITH time zone, text) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."block_venue"(uuid, timestamp WITH time zone, timestamp WITH time zone, text) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."block_venue"(uuid, timestamp WITH time zone, timestamp WITH time zone, text) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."can_reserve_equipment"() TO "authenticated";

REVOKE ALL ON FUNCTION "public"."can_reserve_equipment"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."can_reserve_equipment"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."can_reserve_equipment"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."cancel_equipment_reservation"(uuid) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."cancel_equipment_reservation"(uuid) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."cancel_equipment_reservation"(uuid) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."cancel_equipment_reservation"(uuid) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."cancel_event_request"(integer) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."cancel_event_request"(integer) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."cancel_event_request"(integer) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."cancel_event_request"(integer) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."cancel_planned_event"(integer) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."cancel_planned_event"(integer) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."cancel_planned_event"(integer) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."cancel_planned_event"(integer) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."cancel_venue_booking"(uuid) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."cancel_venue_booking"(uuid) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."cancel_venue_booking"(uuid) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."cancel_venue_booking"(uuid) TO "service_role";

REVOKE ALL ON FUNCTION "public"."change_equipment_reservation"(uuid, integer, boolean) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."change_equipment_reservation"(uuid, integer, boolean) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."change_equipment_reservation"(uuid, integer, boolean) TO "service_role";

REVOKE ALL ON FUNCTION "public"."create_event_from_approved_request"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."create_event_from_approved_request"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."create_event_from_approved_request"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."eligible_event_change_request_events"() TO "authenticated";

REVOKE ALL ON FUNCTION "public"."eligible_event_change_request_events"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."eligible_event_change_request_events"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."eligible_event_change_request_events"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."equipment_availability"(text) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."equipment_availability"(text) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."equipment_availability"(text) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."equipment_availability"(text) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."equipment_events"() TO "authenticated";

REVOKE ALL ON FUNCTION "public"."equipment_events"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."equipment_events"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."equipment_events"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."equipment_peak"(integer, timestamp WITH time zone, timestamp WITH time zone) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."equipment_peak"(integer, timestamp WITH time zone, timestamp WITH time zone) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."equipment_peak"(integer, timestamp WITH time zone, timestamp WITH time zone) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."equipment_request_review_queue"() TO "authenticated";

REVOKE ALL ON FUNCTION "public"."equipment_request_review_queue"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."equipment_request_review_queue"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."equipment_request_review_queue"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."equipment_window_availability"(timestamp WITH time zone, timestamp WITH time zone) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."equipment_window_availability"(timestamp WITH time zone, timestamp WITH time zone) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."equipment_window_availability"(timestamp WITH time zone, timestamp WITH time zone) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."equipment_window_availability"(timestamp WITH time zone, timestamp WITH time zone) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."event_change_request_for_review"(bigint) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."event_change_request_for_review"(bigint) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_change_request_for_review"(bigint) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_change_request_for_review"(bigint) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."event_change_request_impacts"(jsonb) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."event_change_request_impacts"(jsonb) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_change_request_impacts"(jsonb) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_change_request_impacts"(jsonb) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."event_change_requests_for_coordinator"(text) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."event_change_requests_for_coordinator"(text) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_change_requests_for_coordinator"(text) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_change_requests_for_coordinator"(text) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."event_change_requests_for_event"(integer) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."event_change_requests_for_event"(integer) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_change_requests_for_event"(integer) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_change_requests_for_event"(integer) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."event_change_requests_for_organiser"() TO "authenticated";

REVOKE ALL ON FUNCTION "public"."event_change_requests_for_organiser"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_change_requests_for_organiser"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_change_requests_for_organiser"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."event_confirmation_blockers"(public.events) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_confirmation_blockers"(public.events) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_confirmation_blockers"(public.events) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."event_coordinator_lead_dashboard"() TO "authenticated";

REVOKE ALL ON FUNCTION "public"."event_coordinator_lead_dashboard"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_coordinator_lead_dashboard"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_coordinator_lead_dashboard"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."event_registration_roster"(integer) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."event_registration_roster"(integer) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_registration_roster"(integer) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_registration_roster"(integer) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."event_request_assignment_queue"() TO "authenticated";

REVOKE ALL ON FUNCTION "public"."event_request_assignment_queue"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_request_assignment_queue"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_request_assignment_queue"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."event_safety_check_blockers"(public.events) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_safety_check_blockers"(public.events) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_safety_check_blockers"(public.events) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."event_venue_bookings"(integer) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."event_venue_bookings"(integer) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_venue_bookings"(integer) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."event_venue_bookings"(integer) TO "service_role";

REVOKE ALL ON FUNCTION "public"."expire_venue_holds"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."expire_venue_holds"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."expire_venue_holds"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."get_venue_booking"(uuid) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."get_venue_booking"(uuid) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."get_venue_booking"(uuid) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."get_venue_booking"(uuid) TO "service_role";

REVOKE ALL ON FUNCTION "public"."guard_equipment_event"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."guard_equipment_event"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."guard_equipment_event"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."guard_equipment_request_acceptance"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."guard_equipment_request_acceptance"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."guard_equipment_request_acceptance"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."guard_equipment_request_review"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."guard_equipment_request_review"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."guard_equipment_request_review"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."guard_event_lifecycle"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."guard_event_lifecycle"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."guard_event_lifecycle"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."guard_registration_settings"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."guard_registration_settings"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."guard_registration_settings"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."guard_request_lifecycle"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."guard_request_lifecycle"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."guard_request_lifecycle"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."guard_reviewed_equipment_event"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."guard_reviewed_equipment_event"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."guard_reviewed_equipment_event"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."handle_new_auth_user"() TO PUBLIC, "anon", "authenticated";

REVOKE ALL ON FUNCTION "public"."handle_new_auth_user"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."handle_new_auth_user"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."handle_new_auth_user"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."has_booking_role"(text) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."has_booking_role"(text) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."has_booking_role"(text) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."has_booking_role"(text) TO "service_role";

REVOKE ALL ON FUNCTION "public"."has_safety_officer_role"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."has_safety_officer_role"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."has_safety_officer_role"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."hold_venue_booking"(uuid, timestamp WITH time zone) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."hold_venue_booking"(uuid, timestamp WITH time zone) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."hold_venue_booking"(uuid, timestamp WITH time zone) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."hold_venue_booking"(uuid, timestamp WITH time zone) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."list_my_notifications"(integer, integer, integer) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."list_my_notifications"(integer, integer, integer) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."list_my_notifications"(integer, integer, integer) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."list_my_notifications"(integer, integer, integer) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."list_venue_bookings"() TO "authenticated";

REVOKE ALL ON FUNCTION "public"."list_venue_bookings"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."list_venue_bookings"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."list_venue_bookings"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."mark_notification_read"(bigint) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."mark_notification_read"(bigint) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."mark_notification_read"(bigint) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."mark_notification_read"(bigint) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."modify_venue_booking"(uuid, uuid, text) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."modify_venue_booking"(uuid, uuid, text) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."modify_venue_booking"(uuid, uuid, text) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."modify_venue_booking"(uuid, uuid, text) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."my_equipment_request_events"() TO "authenticated";

REVOKE ALL ON FUNCTION "public"."my_equipment_request_events"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."my_equipment_request_events"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."my_equipment_request_events"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."my_equipment_reservations"() TO "authenticated";

REVOKE ALL ON FUNCTION "public"."my_equipment_reservations"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."my_equipment_reservations"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."my_equipment_reservations"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."my_event_registrations"() TO "authenticated";

REVOKE ALL ON FUNCTION "public"."my_event_registrations"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."my_event_registrations"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."my_event_registrations"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."notify_coordinator_assignment"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."notify_coordinator_assignment"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."notify_coordinator_assignment"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."notify_event_request_submitted"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."notify_event_request_submitted"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."notify_event_request_submitted"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."notify_event_staff_assigned"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."notify_event_staff_assigned"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."notify_event_staff_assigned"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."notify_role"(text, text, text, text, text) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."notify_role"(text, text, text, text, text) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."notify_role"(text, text, text, text, text) TO "service_role";

REVOKE ALL ON FUNCTION "public"."notify_user"(uuid, text, text, text, text) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."notify_user"(uuid, text, text, text, text) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."notify_user"(uuid, text, text, text, text) TO "service_role";

REVOKE ALL ON FUNCTION "public"."notify_venue_booking_change"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."notify_venue_booking_change"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."notify_venue_booking_change"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."random_user_with_role"(text[]) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."random_user_with_role"(text[]) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."random_user_with_role"(text[]) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."reassign_event_coordinator_for_lead"(integer, uuid) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."reassign_event_coordinator_for_lead"(integer, uuid) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."reassign_event_coordinator_for_lead"(integer, uuid) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."reassign_event_coordinator_for_lead"(integer, uuid) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."reassign_submitted_request_coordinator"(bigint, uuid) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."reassign_submitted_request_coordinator"(bigint, uuid) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."reassign_submitted_request_coordinator"(bigint, uuid) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."reassign_submitted_request_coordinator"(bigint, uuid) TO "service_role";

REVOKE ALL ON FUNCTION "public"."record_event_status_change"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."record_event_status_change"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."record_event_status_change"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."record_safety_decision"(integer, text, text, text[]) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."record_safety_decision"(integer, text, text, text[]) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."record_safety_decision"(integer, text, text, text[]) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."record_safety_decision"(integer, text, text, text[]) TO "service_role";

REVOKE ALL ON FUNCTION "public"."refresh_arranged_event"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."refresh_arranged_event"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."refresh_arranged_event"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."refresh_venue_event_statuses"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."refresh_venue_event_statuses"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."refresh_venue_event_statuses"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."refresh_visible_event_statuses"() TO "authenticated";

REVOKE ALL ON FUNCTION "public"."refresh_visible_event_statuses"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."refresh_visible_event_statuses"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."refresh_visible_event_statuses"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."register_for_event"(integer, text, text, text) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."register_for_event"(integer, text, text, text) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."register_for_event"(integer, text, text, text) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."register_for_event"(integer, text, text, text) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."release_venue_hold"(uuid) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."release_venue_hold"(uuid) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."release_venue_hold"(uuid) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."release_venue_hold"(uuid) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."reservable_equipment_events"() TO "authenticated";

REVOKE ALL ON FUNCTION "public"."reservable_equipment_events"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."reservable_equipment_events"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."reservable_equipment_events"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."reserve_equipment"(text, integer, integer) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."reserve_equipment"(text, integer, integer) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."reserve_equipment"(text, integer, integer) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."reserve_equipment"(text, integer, integer) TO "service_role";

REVOKE ALL ON FUNCTION "public"."reserve_equipment_assigned"(text, integer, integer) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."reserve_equipment_assigned"(text, integer, integer) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."reserve_equipment_assigned"(text, integer, integer) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."reserve_equipment_for_request"(integer, integer, integer) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."reserve_equipment_for_request"(integer, integer, integer) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."reserve_equipment_for_request"(integer, integer, integer) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."reserve_equipment_for_request"(integer, integer, integer) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."review_equipment_request"(integer, text, integer, integer, text) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."review_equipment_request"(integer, text, integer, integer, text) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."review_equipment_request"(integer, text, integer, integer, text) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."review_equipment_request"(integer, text, integer, integer, text) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."review_event_change_request"(bigint, text, text) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."review_event_change_request"(bigint, text, text) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."review_event_change_request"(bigint, text, text) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."review_event_change_request"(bigint, text, text) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."review_venue_booking"(uuid, text, text) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."review_venue_booking"(uuid, text, text) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."review_venue_booking"(uuid, text, text) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."review_venue_booking"(uuid, text, text) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."safety_review_event"(integer) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."safety_review_event"(integer) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."safety_review_event"(integer) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."safety_review_event"(integer) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."safety_review_queue"() TO "authenticated";

REVOKE ALL ON FUNCTION "public"."safety_review_queue"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."safety_review_queue"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."safety_review_queue"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."set_event_registration_period"(integer, timestamp WITH time zone, timestamp WITH time zone, boolean) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."set_event_registration_period"(integer, timestamp WITH time zone, timestamp WITH time zone, boolean) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."set_event_registration_period"(integer, timestamp WITH time zone, timestamp WITH time zone, boolean) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."set_event_registration_period"(integer, timestamp WITH time zone, timestamp WITH time zone, boolean) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."set_event_registration_ready"(integer, boolean) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."set_event_registration_ready"(integer, boolean) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."set_event_registration_ready"(integer, boolean) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."set_event_registration_ready"(integer, boolean) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."set_updated_at"() TO PUBLIC, "anon", "authenticated";

REVOKE ALL ON FUNCTION "public"."set_updated_at"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."set_updated_at"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."set_updated_at"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."set_venue_booking_occupied"() TO PUBLIC, "anon", "authenticated";

REVOKE ALL ON FUNCTION "public"."set_venue_booking_occupied"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."set_venue_booking_occupied"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."set_venue_booking_occupied"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."submit_event_change_request"(integer, text, jsonb, timestamp WITH time zone, boolean) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."submit_event_change_request"(integer, text, jsonb, timestamp WITH time zone, boolean) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."submit_event_change_request"(integer, text, jsonb, timestamp WITH time zone, boolean) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."submit_event_change_request"(integer, text, jsonb, timestamp WITH time zone, boolean) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."submit_event_for_safety_checks"(integer) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."submit_event_for_safety_checks"(integer) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."submit_event_for_safety_checks"(integer) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."submit_event_for_safety_checks"(integer) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."submit_venue_booking"(jsonb) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."submit_venue_booking"(jsonb) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."submit_venue_booking"(jsonb) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."submit_venue_booking"(jsonb) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."track_venue_update"() TO PUBLIC, "anon", "authenticated";

REVOKE ALL ON FUNCTION "public"."track_venue_update"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."track_venue_update"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."track_venue_update"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."unblock_venue"(uuid) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."unblock_venue"(uuid) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."unblock_venue"(uuid) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."unblock_venue"(uuid) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."update_equipment_reservation"(uuid, integer) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."update_equipment_reservation"(uuid, integer) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."update_equipment_reservation"(uuid, integer) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."update_equipment_reservation"(uuid, integer) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."venue_availability"(uuid, timestamp WITH time zone, timestamp WITH time zone) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."venue_availability"(uuid, timestamp WITH time zone, timestamp WITH time zone) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."venue_availability"(uuid, timestamp WITH time zone, timestamp WITH time zone) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."venue_availability"(uuid, timestamp WITH time zone, timestamp WITH time zone) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."venue_block_summary"(public.venue_blocks) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."venue_block_summary"(public.venue_blocks) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."venue_block_summary"(public.venue_blocks) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."venue_block_summary"(public.venue_blocks) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."venue_booking_conflicts"(uuid, timestamp WITH time zone, timestamp WITH time zone, uuid, boolean) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."venue_booking_conflicts"(uuid, timestamp WITH time zone, timestamp WITH time zone, uuid, boolean) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."venue_booking_conflicts"(uuid, timestamp WITH time zone, timestamp WITH time zone, uuid, boolean) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."venue_booking_conflicts"(uuid, timestamp WITH time zone, timestamp WITH time zone, uuid, boolean) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."venue_booking_summary"(public.venue_booking_requests) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."venue_booking_summary"(public.venue_booking_requests) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."venue_booking_summary"(public.venue_booking_requests) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."venue_booking_summary"(public.venue_booking_requests) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."venue_shortfalls_for_event"(public.venues, public.events) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."venue_shortfalls_for_event"(public.venues, public.events) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."venue_shortfalls_for_event"(public.venues, public.events) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."venue_shortfalls_for_event"(public.venues, public.events) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."venue_unavailability"(timestamp WITH time zone, timestamp WITH time zone) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."venue_unavailability"(timestamp WITH time zone, timestamp WITH time zone) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."venue_unavailability"(timestamp WITH time zone, timestamp WITH time zone) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."venue_unavailability"(timestamp WITH time zone, timestamp WITH time zone) TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."visible_venue_bookings"() TO "authenticated";

REVOKE ALL ON FUNCTION "public"."visible_venue_bookings"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."visible_venue_bookings"() TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."visible_venue_bookings"() TO "service_role";

GRANT EXECUTE ON FUNCTION "public"."withdraw_event_registration"(integer) TO "authenticated";

REVOKE ALL ON FUNCTION "public"."withdraw_event_registration"(integer) FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."withdraw_event_registration"(integer) TO "postgres";

GRANT EXECUTE ON FUNCTION "public"."withdraw_event_registration"(integer) TO "service_role";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."equipment_equipment_id_seq" TO "anon", "authenticated";

REVOKE ALL ON SEQUENCE "public"."equipment_equipment_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."equipment_equipment_id_seq" TO "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."equipment_equipment_id_seq" TO "service_role";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."equipment_request_equipment_request_id_seq" TO "anon", "authenticated";

REVOKE ALL ON SEQUENCE "public"."equipment_request_equipment_request_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."equipment_request_equipment_request_id_seq" TO "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."equipment_request_equipment_request_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."event_activity_activity_id_seq" FROM "anon";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_activity_activity_id_seq" TO "anon";

REVOKE ALL ON SEQUENCE "public"."event_activity_activity_id_seq" FROM "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_activity_activity_id_seq" TO "authenticated";

REVOKE ALL ON SEQUENCE "public"."event_activity_activity_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_activity_activity_id_seq" TO "postgres";

REVOKE ALL ON SEQUENCE "public"."event_activity_activity_id_seq" FROM "service_role";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_activity_activity_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."event_change_request_event_change_request_id_seq" FROM "anon";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_change_request_event_change_request_id_seq" TO "anon";

REVOKE ALL ON SEQUENCE "public"."event_change_request_event_change_request_id_seq" FROM "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_change_request_event_change_request_id_seq" TO "authenticated";

REVOKE ALL ON SEQUENCE "public"."event_change_request_event_change_request_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_change_request_event_change_request_id_seq" TO "postgres";

REVOKE ALL ON SEQUENCE "public"."event_change_request_event_change_request_id_seq" FROM "service_role";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_change_request_event_change_request_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."event_request_amendment_amendment_id_seq" FROM "anon";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_request_amendment_amendment_id_seq" TO "anon";

REVOKE ALL ON SEQUENCE "public"."event_request_amendment_amendment_id_seq" FROM "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_request_amendment_amendment_id_seq" TO "authenticated";

REVOKE ALL ON SEQUENCE "public"."event_request_amendment_amendment_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_request_amendment_amendment_id_seq" TO "postgres";

REVOKE ALL ON SEQUENCE "public"."event_request_amendment_amendment_id_seq" FROM "service_role";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_request_amendment_amendment_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."event_request_event_request_id_seq" FROM "anon";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_request_event_request_id_seq" TO "anon";

REVOKE ALL ON SEQUENCE "public"."event_request_event_request_id_seq" FROM "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_request_event_request_id_seq" TO "authenticated";

REVOKE ALL ON SEQUENCE "public"."event_request_event_request_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_request_event_request_id_seq" TO "postgres";

REVOKE ALL ON SEQUENCE "public"."event_request_event_request_id_seq" FROM "service_role";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_request_event_request_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."event_request_review_review_id_seq" FROM "anon";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_request_review_review_id_seq" TO "anon";

REVOKE ALL ON SEQUENCE "public"."event_request_review_review_id_seq" FROM "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_request_review_review_id_seq" TO "authenticated";

REVOKE ALL ON SEQUENCE "public"."event_request_review_review_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_request_review_review_id_seq" TO "postgres";

REVOKE ALL ON SEQUENCE "public"."event_request_review_review_id_seq" FROM "service_role";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."event_request_review_review_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."events_event_id_seq" FROM "anon";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."events_event_id_seq" TO "anon";

REVOKE ALL ON SEQUENCE "public"."events_event_id_seq" FROM "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."events_event_id_seq" TO "authenticated";

REVOKE ALL ON SEQUENCE "public"."events_event_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."events_event_id_seq" TO "postgres";

REVOKE ALL ON SEQUENCE "public"."events_event_id_seq" FROM "service_role";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."events_event_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."notifications_notification_id_seq" FROM "anon";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."notifications_notification_id_seq" TO "anon";

REVOKE ALL ON SEQUENCE "public"."notifications_notification_id_seq" FROM "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."notifications_notification_id_seq" TO "authenticated";

REVOKE ALL ON SEQUENCE "public"."notifications_notification_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."notifications_notification_id_seq" TO "postgres";

REVOKE ALL ON SEQUENCE "public"."notifications_notification_id_seq" FROM "service_role";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."notifications_notification_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."operational_safety_decision_safety_decision_id_seq" FROM "anon";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."operational_safety_decision_safety_decision_id_seq" TO "anon";

REVOKE ALL ON SEQUENCE "public"."operational_safety_decision_safety_decision_id_seq" FROM "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."operational_safety_decision_safety_decision_id_seq" TO "authenticated";

REVOKE ALL ON SEQUENCE "public"."operational_safety_decision_safety_decision_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."operational_safety_decision_safety_decision_id_seq" TO "postgres";

REVOKE ALL ON SEQUENCE "public"."operational_safety_decision_safety_decision_id_seq" FROM "service_role";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."operational_safety_decision_safety_decision_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."registration_email_outbox_id_seq" FROM "anon";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."registration_email_outbox_id_seq" TO "anon";

REVOKE ALL ON SEQUENCE "public"."registration_email_outbox_id_seq" FROM "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."registration_email_outbox_id_seq" TO "authenticated";

REVOKE ALL ON SEQUENCE "public"."registration_email_outbox_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."registration_email_outbox_id_seq" TO "postgres";

REVOKE ALL ON SEQUENCE "public"."registration_email_outbox_id_seq" FROM "service_role";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."registration_email_outbox_id_seq" TO "service_role";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."roles_role_id_seq" TO "anon", "authenticated";

REVOKE ALL ON SEQUENCE "public"."roles_role_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."roles_role_id_seq" TO "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."roles_role_id_seq" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."equipment" TO "authenticated";

REVOKE ALL ON TABLE "public"."equipment" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."equipment" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."equipment" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."equipment_request" TO "authenticated";

REVOKE ALL ON TABLE "public"."equipment_request" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."equipment_request" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."equipment_request" TO "service_role";

REVOKE ALL ON TABLE "public"."equipment_reservations" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."equipment_reservations" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."equipment_reservations" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."event_activity" TO "anon", "authenticated";

REVOKE ALL ON TABLE "public"."event_activity" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."event_activity" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."event_activity" TO "service_role";

REVOKE ALL ON TABLE "public"."event_change_request" FROM "anon";

GRANT MAINTAIN, REFERENCES, SELECT, TRIGGER ON TABLE "public"."event_change_request" TO "anon";

REVOKE ALL ON TABLE "public"."event_change_request" FROM "authenticated";

GRANT MAINTAIN, REFERENCES, SELECT, TRIGGER ON TABLE "public"."event_change_request" TO "authenticated";

REVOKE ALL ON TABLE "public"."event_change_request" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."event_change_request" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."event_change_request" TO "service_role";

REVOKE ALL ON TABLE "public"."event_registration" FROM "authenticated";

GRANT SELECT ON TABLE "public"."event_registration" TO "authenticated";

REVOKE ALL ON TABLE "public"."event_registration" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."event_registration" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."event_registration" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."event_request" TO "authenticated";

REVOKE ALL ON TABLE "public"."event_request" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."event_request" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."event_request" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."event_request_amendment" TO "authenticated";

REVOKE ALL ON TABLE "public"."event_request_amendment" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."event_request_amendment" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."event_request_amendment" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."event_request_review" TO "authenticated";

REVOKE ALL ON TABLE "public"."event_request_review" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."event_request_review" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."event_request_review" TO "service_role";

REVOKE ALL ("event_coordinator_id") ON TABLE "public"."events" FROM "authenticated";

GRANT UPDATE ("event_coordinator_id") ON TABLE "public"."events" TO "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."events" TO "authenticated";

REVOKE ALL ON TABLE "public"."events" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."events" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."events" TO "service_role";

REVOKE ALL ON TABLE "public"."notifications" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."notifications" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."notifications" TO "service_role";

REVOKE ALL ON TABLE "public"."operational_safety_decision" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."operational_safety_decision" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."operational_safety_decision" TO "service_role";

REVOKE ALL ON TABLE "public"."registration_email_outbox" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."registration_email_outbox" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."registration_email_outbox" TO "service_role";

REVOKE ALL ON TABLE "public"."roles" FROM "anon";

GRANT MAINTAIN, REFERENCES, SELECT, TRIGGER ON TABLE "public"."roles" TO "anon";

REVOKE ALL ON TABLE "public"."roles" FROM "authenticated";

GRANT MAINTAIN, REFERENCES, SELECT, TRIGGER ON TABLE "public"."roles" TO "authenticated";

REVOKE ALL ON TABLE "public"."roles" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."roles" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."roles" TO "service_role";

REVOKE ALL ON TABLE "public"."user_roles" FROM "anon";

GRANT MAINTAIN, REFERENCES, SELECT, TRIGGER ON TABLE "public"."user_roles" TO "anon";

REVOKE ALL ON TABLE "public"."user_roles" FROM "authenticated";

GRANT MAINTAIN, REFERENCES, SELECT, TRIGGER ON TABLE "public"."user_roles" TO "authenticated";

REVOKE ALL ON TABLE "public"."user_roles" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."user_roles" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."user_roles" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."users" TO "authenticated";

REVOKE ALL ON TABLE "public"."users" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."users" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."users" TO "service_role";

REVOKE ALL ON TABLE "public"."venue_blocks" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."venue_blocks" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."venue_blocks" TO "service_role";

REVOKE ALL ON TABLE "public"."venue_booking_requests" FROM "authenticated";

GRANT SELECT ON TABLE "public"."venue_booking_requests" TO "authenticated";

REVOKE ALL ON TABLE "public"."venue_booking_requests" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."venue_booking_requests" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."venue_booking_requests" TO "service_role";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."venues" TO "authenticated";

REVOKE ALL ON TABLE "public"."venues" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."venues" TO "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."venues" TO "service_role";

SELECT cron.schedule_in_database('connectsphere-expire-venue-holds', '* * * * *', 'select public.expire_venue_holds()', 'postgres', NULL, true);

