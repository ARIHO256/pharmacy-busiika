# HealthPilot Design System

The palette extends the supplied flow-chart colours into semantic application tokens. Colour supports meaning but must never be the only status indicator.

## Core brand palette

| Token | Hex | Use |
|---|---:|---|
| Primary 950 | `#071E48` | deepest navigation/background |
| Primary 900 | `#0A2D66` | headings and dark brand surfaces |
| Primary 800 | `#123F86` | strong interactive states |
| Primary 700 | `#1653A5` | main brand blue |
| Primary 600 | `#2468C4` | primary action/link |
| Primary 500 | `#3B82D0` | icons/highlights |
| Primary 100 | `#EAF3FC` | selected cards/status backgrounds |
| Primary 50 | `#F4F8FD` | page section background |

## Clinical/service colours

| Meaning | Strong | Light surface |
|---|---:|---:|
| Appointment/success | `#4F8A3D` | `#F1F8EE` |
| Communication | `#6F42C1` | `#F4F0FC` |
| Payment | `#E87822` | `#FFF4EC` |
| Laboratory | `#6A35B5` | `#F5F0FC` |
| Hospital | `#178A94` | `#ECF8F8` |
| Insurance | `#E36A24` | `#FFF2EA` |
| Warning | `#D99A16` | `#FFF8E5` |
| Danger/critical | `#C83B3B` | `#FFF0F0` |

## Neutrals

| Token | Hex |
|---|---:|
| Primary text | `#13233A` |
| Secondary text | `#536278` |
| Muted text | `#7E8998` |
| Border | `#D6DEE8` |
| Divider | `#E7ECF2` |
| Page | `#F7F9FC` |
| Surface | `#FFFFFF` |

## Interaction requirements

- body text should normally be at least 16 px for patient-critical content;
- touch targets should be generous and keyboard reachable;
- every input needs a visible label;
- focus rings must remain visible;
- status must include text/icon in addition to colour;
- critical and destructive actions require explicit wording;
- respect reduced-motion preferences;
- use plain language for patient flows;
- do not place diagnoses, prescriptions or sensitive results in notification previews by default.

## Information architecture

Patient primary navigation:

```text
Dashboard • Find Doctors • Appointments • Health Record • Messages
Prescriptions • Pharmacy • Lab Tests • Hospitals • Insurance • Invoices • Profile
```

Do not add every future module to the main navigation. Use contextual care journeys and a service launcher to keep the super app understandable.
