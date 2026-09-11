![](data:image/png;base64...)

**IS212 (AY 2026/27 T1) – Customer Briefing**

**\*\* Please Read This First \*\***

For the IS212 project, you will build the first release of a system using the scrum process.

In this document, you will find a briefing from the (mock) customer describing their desired system.

Please note that -

This customer briefing is (initially) **<u>deliberately ambiguous.</u> Why?** No real-world customer knows *precisely* what they want on day 1, and there may be edge cases or conflicting expectations that have not yet been considered.

You can disambiguate the briefing by 'meeting' the customer (role played by your section's instructor) during the scheduled Q&A sessions over the next few weeks. Questions through other channels will <u>not</u> be answered.

**Each section has a different 'customer'.** Please <u>only</u> consider clarifications provided by your section's customer, as clarifications in other sections may not be consistent.

The customer briefing is quite wide-ranging. Don't panic! You will NOT build the entire system. The customer **will eventually clarify the core functionalities to cover in your first release** (i.e., your Week 12 submission). Wait for these to be identified in Week 4 before you start coding, and work on creating epics/user stories for your product backlog in the meantime.

The IS212 project instructions will be released on Friday, Week 3 (6pm). These instructions will list the artefacts expected in your submission and the grading rubrics, which emphasise the **<u>scrum process, requirements discovery, software quality, and your documentation of these activities</u>** more than the final product alone.

Until the project instructions are released, use Weeks 2-4 to understand the customer's needs and translate them into a product backlog of epics and user stories. We do not recommend sprinting until Week 4, especially as the customer has not yet identified the core functionalities to be implemented in the first release.

**Customer Briefing: Event Planning and Venue Booking System**

**1. Organisation**

ConnectSphere Event Services is a regional organisation that provides professional event planning and venue services to organisations across Southeast Asia. The company organises a wide variety of events, such as conferences, seminars, workshops, etc.

It operates and owns several event facilities within Singapore. ConnectSphere also maintains equipment and supporting resources commonly required for events. ConnectSphere currently has approximately 500 staff for its operations, taking on the role of **Event Coordinators**, **Venue Staff**, and **Technical Support Staff**.

As the organization expands, the number of events, venues, resources, clients, and participants that must be coordinated has increased significantly. ConnectSphere would therefore like to modernise the way it manages its events.

The proposed system will be used by internal and external users.

**2. Background**

ConnectSphere currently relies on a mixture of email, spreadsheets, shared calendars, messaging applications, online forms, and manually maintained documents to organise events. Information for a single event may therefore be spread across several places and managed by different employees.

A typical event begins when an external **Event Organiser** approaches ConnectSphere with an event to host or support. The Event Organiser is responsible for providing the initial requirements and communicating with ConnectSphere about the event, and provides preliminary information such as the purpose and type of event, preferred date and time, expected number of attendees, general programme, room-layout preferences, accessibility requirements, equipment requirements, registration requirements, and any other special arrangements.

An **Event Coordinator** is then assigned to the request and acts as the main liaison for the Event Organiser, who will review the request and contact the Event Organiser for any clarifications and coordination before confirmation.

For example, the Event Organiser may request a "large room" without specifying the expected attendance or may request a hybrid event without explaining what video-conferencing facilities are required.

Once the basic requirements are sufficiently clear, the Event Coordinator works with **Venue Staff** to identify a suitable venue. Venue Staff maintain information about ConnectSphere's rooms and spaces and are responsible for deciding whether the requested venue can be made available for the event.

Venue suitability may depend on several factors, such as the proposed date and time, maximum capacity, supported room layouts, accessibility, available facilities, existing bookings, operating hours, setup requirements, and the turnaround time required between consecutive events. A venue may also be unavailable because of maintenance, renovation, safety restrictions, or another internal activity.

Some events also require technical equipment and support. In these cases, **Technical Support Staff** review the requested equipment and technical support. They maintain records of available equipment, determine whether sufficient equipment can be reserved, and may also be assigned to support an event on-site.

Equipment may already be reserved for another event, located at another venue, damaged, or undergoing maintenance. The planning process may therefore involve several rounds of communication before an event can be confirmed.

Once the essential arrangements have been made, the Event Coordinator can confirm the event with the Event Organiser. For events that require registration, Attendees may subsequently register through the system and receive the event information.

Changes frequently occur after an event has been proposed or even after it has been confirmed. For example:

* The Event Organiser may request a different date or time.
* Expected attendance may increase or decrease.
* Additional equipment or technical support may be requested.
* The programme may be extended, shortened, or split into multiple sessions.
* A booked venue may become unavailable because of an operational issue.
* Reserved equipment may become unavailable because of damage or maintenance.
* The Event Organiser may postpone or cancel the event due to unforeseen circumstances.
* Registration numbers may reach the event capacity earlier than expected.

Such changes can affect arrangements that have already been made. Increasing attendance from 80 to 150 people may make the selected venue unsuitable. Changing an event date may create a venue or equipment conflict. Extending an event may affect the turnaround time needed before another booking. ConnectSphere therefore expects the proposed system to help users identify and manage these relationships.

The current process creates several difficulties:

* Event requests may be incomplete, duplicated, or difficult to track.
* Event Coordinators may maintain separate spreadsheets or personal notes, creating different versions of the same event information.
* Event Organisers may be unsure whether an event, venue, or equipment arrangement has been approved or confirmed.
* Venue Staff may receive incomplete or outdated event requirements.
* The same venue or equipment may accidentally be considered available for more than one event.
* Insufficient setup or turnaround time may be left between consecutive events.
* Last-minute changes may not reach all affected staff or attendees.
* Cancelled events may continue to occupy venue or equipment reservations.
* Technical Support Staff may receive insufficient notice about upcoming equipment or support requirements.
* Attendees may receive outdated dates, times, or venue information after an event changes.
* It is difficult to identify which upcoming events still have incomplete arrangements.
* It is difficult to determine who changed important event information and when the change occurred.

ConnectSphere would therefore like to develop a custom-built Event Planning and Venue Booking System that provides a single platform for its processes.

**3. Target group of users**

The system will be used by ConnectSphere and external users. The roles below are the roles referred to throughout this customer briefing.

| **Role** | **Internal / External** | **Main Responsibility** |
| --- | --- | --- |
| Event Organiser | External | Client representative who has an event to organize and communicates event requirements to ConnectSphere. |
| Event Coordinator | Internal | They are assigned to coordinate the overall planning of an event and act as the main internal point of contact. |
| Venue Staff | Internal | They are responsible for venue information, availability, booking decisions, and physical venue preparation. |
| Technical Support Staff | Internal | They are responsible for equipment, technical requirements, equipment reservations, and technical support for events. |
| Attendee | External | Participant who registers for and attends an event. |

**4. Application features**

The following describes the broad functionality ConnectSphere is considering for the proposed system. The customer briefing is intentionally wide-ranging, and the first software release may not implement every functionality described below.

| **Functionality Area** | **Description** |
| --- | --- |
| User Authorisation and Authentication | Allow users to securely access the system. Access to information and functionality depends on whether the user is an Event Organiser, Event Coordinator, Venue Staff member, Technical Support Staff member, or Attendee. |
| User Profile Management | Users can maintain relevant profile information such as name, organisation, contact details, and communication preferences. Internal users may also have information relating to their department or responsibilities. |
| Client Management | ConnectSphere can maintain information about external client organisations. Multiple Event Organisers may belong to the same organisation, and an organisation may have several past and upcoming events. |
| Event Request Creation | Event Organisers can create event requests containing information such as the event name, description, purpose, preferred dates, expected attendance, venue requirements, accessibility needs, and other planning information. |
| Draft Event Requests | Event Organisers can save an event request before submission so that incomplete information can be completed or reviewed later. |
| Event Categories | Events can be classified into categories such as conference, workshop, training session, exhibition, meeting, seminar, networking event, or any other type defined by ConnectSphere. |
| Event Review and Approval | Event Coordinators can review submitted requests, request amendments or clarification, approve requests, or reject requests where appropriate. |
| Coordinator Assignment | Events can be assigned to an Event Coordinator responsible for managing the planning process. Reassignment may be required when staff responsibilities or availability change. |
| Event Status Management | Events progress through suitable statuses so that users can understand their current stage, for example draft, submitted, under review, approved, planning, awaiting arrangements, confirmed, completed, cancelled, or rejected. |
| Event Information Management | Authorised users can update relevant event information during planning. The system should distinguish between ordinary edits and changes that may affect arrangements already confirmed. |
| Event Programme and Agenda | Event Organisers or Event Coordinators can record the programme for an event, including sessions, breaks, presentations, or other scheduled activities. |
| Multi-Session Events | Some events may contain several sessions within the same day or across multiple days. Sessions may have different timings or operational requirements. |

| **Functionality Area** | **Description** |
| --- | --- |
| Recurring or Similar Events | Where useful, information from a previous or recurring event may be reused to reduce repeated data entry, while still allowing the new event to have different dates and requirements. |
| Comments and Discussion | Event Organisers and relevant internal users can exchange comments, questions, and updates relating to an event so that important planning conversations are retained with the event record. |
| Supporting Documents | Users can attach documents relevant to an event, such as programmes, floor plans, presentation requirements, or other supporting materials. |
| Venue Catalogue | The system maintains information about ConnectSphere venues, including location, capacity, facilities, accessibility, supported room layouts, operating hours, and other important characteristics. |
| Venue Availability Calendar | Authorised users can view when venues are available, tentatively held, confirmed, blocked, or otherwise unavailable. |
| Venue Search and Filtering | Event Coordinators can search for potential venues using requirements such as date, time, attendance, location, capacity, accessibility, supported layout, and required facilities. |
| Venue Suitability Checking | The system should assist users in identifying whether a venue appears suitable for an event. For example, a venue should not normally be treated as suitable when expected attendance exceeds its capacity. |
| Venue Booking Request | An Event Coordinator can request a venue for an event. The request contains the relevant event timing and venue requirements for Venue Staff to review. |
| Venue Booking Approval | Venue Staff can approve or reject a venue booking request and may provide a reason or suggest an alternative arrangement. |
| Tentative Venue Holding | Where permitted by ConnectSphere's business process, a venue may be temporarily held while an event is still being finalised. The rules governing tentative holds may differ from confirmed bookings. |
| Booking Conflict Detection | The system should identify incompatible or overlapping venue bookings and help prevent double-booking. |
| Setup and Turnaround Time | Venue availability may need to consider preparation before an event and reset time after an event, rather than only the published event start and end times. |

| **Functionality Area** | **Description** |
| --- | --- |
| Venue Unavailability Management | Venue Staff can block venues because of maintenance, renovation, safety issues, internal activities, or other operational reasons. |
| Room Layout Management | Event requirements may include layouts such as classroom, theatre, boardroom, banquet, exhibition, or another arrangement. Venue Staff can record which layouts are supported by each venue. |
| Event Capacity Management | Expected attendance and venue capacity should be considered throughout planning. A significant attendance change may require the suitability of an existing venue booking to be reviewed. |
| Equipment Catalogue | The system maintains information about equipment available for events, including type, description, quantity, location, and operational status. |
| Equipment Request Management | Event Coordinators can record equipment required for an event, including quantities and relevant technical requirements. |
| Equipment Availability Checking | Technical Support Staff can determine whether sufficient suitable equipment is available for the required date and time. |
| Equipment Reservation | Available equipment can be reserved for an event so that the same limited equipment is not simultaneously committed to incompatible events. |
| Equipment Maintenance Status | Equipment that is damaged, being repaired, or otherwise unavailable should not be treated as available for event use. |
| Technical Support Requests | Event Coordinators can indicate when an event requires technical support before or during the event and describe the support required. |
| Technical Staff Assignment | Where required, suitable Technical Support Staff can be allocated to support an event according to availability and event requirements. |
| Event Readiness Tracking | Event Coordinators can determine whether important arrangements such as venue, equipment, technical support, programme, and registration setup are ready. |
| Outstanding Action Tracking | The system can identify planning matters that are incomplete or require action before an event can be confirmed or delivered. |

| **Functionality Area** | **Description** |
| --- | --- |
| Event Confirmation | Once the necessary arrangements have been completed, the Event Coordinator can confirm the event. Confirmed arrangements should be visible to the appropriate users. |
| Attendee Registration | Where enabled, Attendees can register for confirmed events and provide the required registration information. |
| Registration Capacity | Registration may be limited according to the capacity defined for the event. The system should prevent or appropriately handle registrations beyond the permitted capacity. |
| Registration Period | An event may define when registration opens and closes. Attendees should only be able to register when registration is available. |
| Attendee Waiting List | Where supported, additional Attendees may join a waiting list when an event reaches capacity. |
| Registration Withdrawal | Attendees can withdraw their registration where permitted. The released place may subsequently become available to another Attendee. |
| Attendance Recording | ConnectSphere may record whether registered Attendees ultimately attended an event, allowing registration and attendance information to be distinguished. |
| Event Change Requests | Event Organisers can request permitted changes after an event has been submitted or confirmed. The Event Coordinator can review the requested change. |
| Impact of Event Changes | Significant changes, such as date, time, attendance, venue requirements, or equipment requirements, may require existing arrangements to be reviewed again. |
| Rescheduling | Events can be rescheduled where necessary. Existing venue, equipment, technical-support, and attendee arrangements may need to be reconsidered or updated. |
| Cancellation Management | An authorised user can cancel an event. Related venue and equipment reservations should no longer remain committed to a cancelled event, subject to the applicable business rules. |
| Notification System | Users can receive notifications about relevant events such as request submission, clarification requests, approval decisions, booking decisions, confirmation, changes, registration updates, or cancellation. |

| **Functionality Area** | **Description** |
| --- | --- |
| Reminder System | The system may remind relevant users about upcoming events, incomplete arrangements, registration deadlines, preparation activities, or other time-sensitive matters. |
| Event Calendar | Users can view appropriate upcoming events in calendar form. The information shown should depend on their role and access rights. |
| Search and Filtering | Users can search for events using suitable criteria such as event name, client organisation, date, venue, status, category, or assigned coordinator. |
| Activity History | Significant actions are recorded, including who performed the action and when it occurred, to support accountability and troubleshooting. |
| Change History | Users with appropriate access can review how important event information has changed over time. |
| Role-Based Dashboard | The system provides each internal or external role with an overview relevant to its responsibilities, such as events requiring attention, upcoming bookings, equipment requests, or attendee registrations. |
| Event Reports | Appropriate users can generate summaries containing event details, schedule, venue, operational requirements, registration information, and other relevant information. |
| Venue Usage Reports | Internal users can review venue bookings and usage over a selected period to support operational planning. |
| Registration Reports | Event Organisers and Event Coordinators can view or export attendee information where appropriate and subject to access restrictions. |
| Report Generation and Exporting | Suitable reports or event information can be exported into common formats for meetings, operational use, or record-keeping. |

**5. Typical event planning process**

Although events may differ, a typical event is expected to follow a process similar to the one below. The exact business rules for particular steps may be clarified during the customer Q&A sessions.

**Step 1 - Draft Event Request**: An Event Organiser creates a draft request containing the initial event requirements. They may save the request and continue editing it before submission.

**Step 2 - Submission**: The Event Organiser submits the request to ConnectSphere.

**Step 3 - Coordinator Assignment**: An Event Coordinator is assigned to the request and becomes the main ConnectSphere employee responsible for coordinating that event.

**Step 4 - Review and Clarification**: The Event Coordinator reviews the information provided. When information is incomplete or unclear, they request clarification or amendment from the Event Organiser.

**Step 5 - Initial Approval**: Once sufficient information is available, the Event Coordinator determines whether planning should proceed. Rejected or returned requests should retain an appropriate record of the decision.

**Step 6 - Venue Identification**: The Event Coordinator searches for venues that could satisfy the date, time, capacity, layout, accessibility, facilities, and setup requirements of the event.

**Step 7 - Venue Request**: The Event Coordinator submits a venue booking request. Venue Staff review the request and may approve it, reject it, or suggest another venue or arrangement.

**Step 8 - Technical Requirements**: Where equipment or technical support is required and requested by the Event Organiser, Technical Support Staff review the requirements and determine whether suitable resources can be provided and reserved.

**Step 9 - Event Preparation**: The Event Coordinator monitors outstanding arrangements. Venue Staff and Technical Support Staff update the relevant preparation information as work progresses.

**Step 10 - Event Confirmation**: When the essential arrangements have been completed, the Event Coordinator confirms the event. The Event Organiser can then view the confirmed arrangements.

**Step 11 - Attendee Registration**: Where registration is required, Attendees can register for the confirmed event during the permitted registration period and subject to the applicable capacity.

**Step 12 - Changes Before the Event**: The Event Organiser may subsequently request changes. The Event Coordinator determines whether those changes affect venue, equipment, technical-support, registration, or other arrangements.

**Step 13 - Event Delivery**: Venue Staff prepare the venue and Technical Support Staff prepare the necessary equipment or support. Relevant users should be able to access the latest confirmed information.

**Step 14 - Completion**: Once the event has taken place, it can be marked as completed. Relevant attendance information, operational notes, or issues may then be recorded and the event can be closed.

**6. Notifications**

Users should be kept informed when important events or arrangements relevant to them change. Notifications may be provided within the application or through another suitable communication channel.

Examples of situations that may generate a notification include:

A new event request is submitted.

An Event Coordinator is assigned.

Additional information or amendment is requested.

An event request is approved, rejected, or returned.

A venue booking is requested, approved, rejected, or changed.

Requested equipment is confirmed or found to be unavailable.

An event becomes confirmed.

The Event Organiser requests a significant change.

An event is rescheduled, postponed, or cancelled.

Registration opens or closes.

Registration reaches capacity or a waiting-list status changes.

A registered Attendee withdraws where that affects availability.

An upcoming event still has incomplete arrangements.

A venue or equipment availability change affects an upcoming event.

**7. Design**

The system should be both desktop- and mobile-friendly. External users may access the system from personal computers or mobile devices, while internal ConnectSphere staff may need access while preparing event spaces or equipment.

Information should be presented clearly and should not assume that users understand ConnectSphere's internal processes. The current status of an event, its confirmed arrangements, and any outstanding actions should be easy for the appropriate user to understand.

**8. Other requirements**

**a. Performance**

Common operations such as viewing an event, searching available venues, opening a venue calendar, checking equipment availability, or submitting a registration should complete within a reasonable time.

**b. Security**

The system should only allow authorised users to access protected information. Access should depend on the user's role and relationship to an event. For example, an Event Organiser should not normally be able to view events belonging to unrelated clients, and an Attendee should not be able to view internal planning information.

**c. Usability**

All groups of users should be able to complete their common activities without extensive training or guidance.

**d. Reliability and consistency**

The system should maintain consistent information when related event arrangements change. Users should not be presented with contradictory information regarding event dates, venue bookings, equipment availability, or registration status.

**e. Scalability**

The proposed solution should support ConnectSphere's anticipated growth over the next three years, including increases in events, users, client organisations, venues, equipment, and registrations.

**f. Auditability**

Important actions should be recorded. Where appropriate, ConnectSphere should be able to determine what was changed, who changed it, and when the change was made.

**g. Maintainability**

The organisation expects its processes to evolve over time. The proposed system should therefore be designed so that future functionality and business rules can be added without requiring the entire system to be rebuilt.

***Notes:***

The customer will continue to discuss the proposed system with Event Organisers, Event Coordinators, Venue Staff, Technical Support Staff, and other relevant stakeholders. There may be special cases and business rules that have not been described in this initial briefing.

Students are expected to use the scheduled customer Q&A sessions to clarify such matters and develop appropriate epics and user stories. The customer will subsequently identify the functionality considered most important for the first release.

The teaching team will release the exact project deliverables and grading rubrics in Week 4.