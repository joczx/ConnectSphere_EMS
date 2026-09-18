create table public.equipment_request (
  equipment_request_id serial not null,
  event_id integer not null,
  equipment_id integer null,
  requested_by uuid not null,
  reviewed_by uuid null,
  quantity integer not null,
  status character varying(50) not null default 'pending'::character varying,
  technical_requirements text null,
  requested_at timestamp with time zone not null default now(),
  equipment_type character varying(200) not null,
  reason_for_rejection text null,
  constraint equipment_request_pkey primary key (equipment_request_id),
  constraint equipment_request_equipment_id_fkey foreign KEY (equipment_id) references equipment (equipment_id),
  constraint equipment_request_event_id_fkey foreign KEY (event_id) references events (event_id),
  constraint equipment_request_requested_by_fkey foreign KEY (requested_by) references users (user_id),
  constraint equipment_request_reviewed_by_fkey foreign KEY (reviewed_by) references users (user_id),
  constraint equipment_request_quantity_check check ((quantity > 0))
) TABLESPACE pg_default;