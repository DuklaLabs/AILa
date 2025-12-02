
INSERT INTO events.logs (
    event_type,
    user_id,
    machine_id,
    message,
    data_json
)
VALUES (
    'error',
    (SELECT id FROM auth.users WHERE username = 'admin'),
    (SELECT id FROM lab.machines WHERE name = 'Prusa MK4'),
    'Chyba při zpracování úlohy – nedostatek materiálu.',
    jsonb_build_object(
        'error_code', 505,
        'detail', 'Filament se zaseknul',
        'time', NOW()
    )
);