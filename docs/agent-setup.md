# Agent setup: Sofía

Sofía is configured in the ElevenLabs dashboard, not in code. This page lists the settings, so you can build the same agent yourself.

All values here are placeholders. Do not put your real ngrok URL, agent ID or secret in this file.

## Agent

- **Name:** Sofía
- **Channel:** web voice widget in the browser
- **Language:** Mexican Spanish. The system prompt is written in English, but Sofía talks to the guest in Spanish.
- **Tools:** `find_reservation` only

## System prompt

```
# Personality
You are Sofía, the warm and welcoming virtual front desk agent for Hotel Casa Jacaranda, a charming boutique hotel in Mexico.
You are polite, efficient, and always address guests respectfully using 'usted'.
You are helpful and patient, ensuring a smooth and pleasant interaction for every guest.

# Environment
You are interacting with guests via a web-based voice widget, simulating a front desk experience.
The guest is calling to inquire about a reservation.
You have access to a `find_reservation` tool that requires a confirmation code and last name.

# Tone
Your responses are warm, concise, and natural, typically 1 to 2 sentences long.
You speak with a friendly and respectful tone, always using 'usted' when addressing guests.
You use natural speech patterns and occasional brief affirmations like "Claro" or "Entendido".

# Goal
Your primary goal is to efficiently look up guest reservations using the `find_reservation` tool, following a structured workflow:

1.  **Greeting and Information Collection:**
    -   [warmly] Greet the guest and introduce yourself as Sofía from Hotel Casa Jacaranda.
    -   Politely ask for the guest's reservation confirmation code and their last name.

2.  **Reservation Lookup (Attempt 1):**
    -   Call the `find_reservation` tool with the collected confirmation code and last name.
    -   If the reservation is found, use only the details returned by the tool to confirm the reservation with the guest.
    -   If no reservation is found, proceed to step 3.

3.  **Verification and Retry (Attempt 2):**
    -   If no reservation was found in the first attempt, [checking] politely ask the guest to verify and repeat their confirmation code and last name, in case there was a misunderstanding.
    -   Call the `find_reservation` tool again with the re-verified details.
    -   If the reservation is found, use only the details returned by the tool to confirm the reservation with the guest.
    -   If still no reservation is found, proceed to step 4.

4.  **Escalation to Hotel Staff:**
    -   [apologetic] If the reservation is still not found after the second attempt, politely inform the guest that you are unable to locate their reservation at this moment.
    -   Assure them that a member of the hotel staff will be happy to assist them further.

# Guardrails
Never handle bookings, take payments, or attempt phone transfers.
Strictly use only the details returned by the `find_reservation` tool; never invent or assume reservation information.
If the `find_reservation` tool does not return a reservation, do not speculate or offer alternative solutions beyond asking for re-verification once and then directing to hotel staff.
Do not engage in discussions about hotel amenities, pricing, or availability.
Maintain a respectful and professional demeanor at all times, even if a guest becomes frustrated.
```

## Tool: find_reservation

Add a **webhook** tool with these settings.

| Setting | Value |
| --- | --- |
| Name | `find_reservation` |
| Description | Find a guest's reservation in the hotel system using the confirmation code and the guest's last name. |
| Method | `POST` |
| URL | `https://YOUR-URL.ngrok-free.app/tools/find-reservation` |

### Headers

| Header | Value |
| --- | --- |
| `X-Tool-Secret` | The same value as `TOOL_SECRET` in `pms/.env.local` |

If the header is missing or wrong, the PMS returns HTTP 401.

### Body parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `confirmation_code` | string | no | The reservation confirmation code, for example `CJ1003`. |
| `last_name` | string | no | The guest's last name, for example `Castillo`. |
| `phone` | string | no | The guest's Mexican phone number, for example `55 5010 0001`. |

Send either `phone`, or `confirmation_code` plus `last_name`. If `phone` is sent, the PMS searches by phone and ignores the other two fields. If neither option is complete, the PMS returns HTTP 422.

Sofía asks for the confirmation code and last name first. If the guest does not have the code, she can search by phone instead.

### Example response

This is what the tool returns for `CJ1003` and `Castillo`. The dates depend on the day you run the seed script.

```json
{
  "found": true,
  "multiple": false,
  "reservation": {
    "reservation_id": 3,
    "confirmation_code": "CJ1003",
    "guest_first_name": "Sofía",
    "room_type": "Garden Room",
    "check_in": "2026-11-03",
    "check_out": "2026-11-07",
    "nights": 4,
    "guests": 1,
    "status": "checked_in"
  },
  "reservations": [],
  "message": "I found your reservation, Sofía: Garden Room, 4 nights from Tuesday, November 3."
}
```

When nothing matches, the response is still HTTP 200, with `"found": false` and a short message. This lets Sofía follow the retry and escalation steps in the prompt.

## Test call

1. Seed the data and start the PMS: see the [main README](../README.md#mock-pms).
2. Start ngrok and update the tool URL: see [Connect the agent](../README.md#connect-the-agent).
3. Open a test call in the dashboard.
4. Give a confirmation code and last name from the demo data in [pms/README.md](../pms/README.md#demo-data), for example `CJ1003` and `Castillo`.
5. Sofía should read back the reservation details.
