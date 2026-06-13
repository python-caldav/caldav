# Security policy

Issues should be fixed ASAP, and information on any security issue should be published as soon as it's fixed. Serious issues should be reported privately and kept under wraps until a fix is released — use [GitHub's private vulnerability reporting](https://github.com/python-caldav/caldav/security/advisories/new) (the "Report a vulnerability" button on the Security tab), or get in touch with the maintainer via [CONTACT](CONTACT.md) or the [CODE OF CONDUCT](CODE_OF_CONDUCT) file.  Use the public GitHub issue tracker only for non-sensitive issues.

There are no "LTS"-releases of the CalDAV package, but the maintainer will always consider backporting security fixes if it's deemed relevant.  The maintainer is doing most of the maintenance on hobby-basis and may have other things in life preventing him from dealing with issues on the go, so no guarantees are given.

All contributions are carefully reviewed by Tobias Brox, and AI-tools are used for code reviews prior to each release.  All releases are carefully tested and tagged with a PGP-signed commit.

# Known security issues and risks

## RFC6764

**Summary**: If you're using auto-discovery of the CalDAV-URL, anyone controlling your local resolver may try to fish out username and password.

**Mitigation**: Use a URL rather than a domain when configuring the library.  Leave `require_tls`, `ssl_verify_cert` to the default.

I do see a major security flaw with the RFC6764 discovery. If the DNS is not to be trusted, someone can hijack the connection by spoofing the service records, and also spoofing the TLS setting, encouraging the client to connect over plain-text HTTP without certificate validation. Utilizing this it may be possible to steal the credentials. This flaw can be mitigated by using DNSSEC, but DNSSEC is not widely used, and fixing support for DNSSEC validation in the CalDAV library was found to be non-trivial - the work done is now on a stalled pull request.  This has been partly mitigated by adding a `require_tls` connection parameter that is `True` by default, plus by ensuring one isn't routed to a different domain.

Auto-discovery and HTTP redirects also mean the host you end up talking to may not be the one you configured.  If you run the library in a context where it can reach internal/private network resources (server-side request forgery, SSRF), be aware that a malicious DNS resolver or a malicious/compromised server can steer requests towards other hosts.  Configuring an explicit URL rather than relying on domain-based discovery limits this.

## DDoS/OOM risk - recurring events/tasks search

**Summary:** If you allow untrusted parties to specify search-terms towards a calendar containing recurring events/tasks, bad things may happen.

The package offers both client-side and server-side expansion of recurring events and tasks.  It currently does not offer expansion for open-ended date searches - but with a large enough timespan and a frequent enough RRULE, there may be millions of recurrences returned.  Those recurrences are returned as a generator, so things will not break down immediately.  However, there is no guaranteed sort order of the recurrences ... and once you add sorting parameters to the search, bad things may happen.

## XML parsing

**Summary:** XML responses are parsed defensively by default; only relax this against servers you trust.

The library parses XML responses from the server using lxml.  By default the parser is configured to resist common XML attacks: external entity resolution is disabled (`resolve_entities=False`) and network access during parsing is blocked (`no_network=True`), guarding against XXE (XML External Entity) attacks, and lxml's built-in limits protect against oversized "billion laughs"-style entity-expansion payloads.

The `huge_tree` connection option (default off) disables lxml's built-in parser limits so that very large calendar objects can be handled.  With `huge_tree` enabled, a malicious or compromised server can exhaust available memory with a crafted XML payload — only enable it against servers you trust.  See the [lxml XMLParser documentation](https://lxml.de/api/lxml.etree.XMLParser-class.html).

## Bugs causing weird things happening

**Summary:** Always expect the unexpected

Weird things may happen due to bugs both on in the CalDAV package, on your side and on the server side.  Some anecdotes from using Zimbra:

* I once tried to restore from backup and push ten years of ical code to the calendar server.  The calendar server responded by re-inviting people to the meetings we had ten years ago.  I'm inclined to call that a server side bug - but it also highlights the risk of using the CalDAV library for doing operations that ordinary calendaring clients aren't doing.
* It's been observed that cancelling participation in an event caused the event to be cancelled for all participants (even if the person deciding to not go to the event was not an organizer and should have no permissions to edit the event).  Clearly a server-side issue.

## Other things to consider

**Summary:** Beware of risks and exposure when creating applications:

* Your code may handle username and password, be careful not to expose such credentials.  Even the URL to the calendar server and/or calendar may be something people want to keep private.  The library includes code for reading this data from a standard config file - please use it rather than reinventing the wheel or hard-coding credentials directly into your code.
* Consider that calendar events and such is personal data, which deserves protection.  In the EU with the GDPR, such protection is even mandated by law.
* If you allow arbitrary people to create calendar content to be saved to a server, there may be some risks involved:
  * Depending on the server implementation, it may be possible to use the caldav library for sending spam emails.
  * Be aware of DoS-attacks: By storing too much / too big / specially crafted icalendar data, the server and/or client may crash or consume all available resources.
  * If allowing anonymous parties to save and retrieve data from your server, you may end up with responsibility for spreading illicit information.  This may include things like child sexual abuse material.  Political or religious propaganda may be legitimate and legal in some countries, but may involve death penalty in other countries.  Your calendar server may also be used for coordinating criminal activity.
* If you allow arbitrary people to fetch calendar content from the server, there may also be some risks involved - see the separate section on DoS-attack by requesting a large time span of expanded events.

## Supply attack risk

**Summary:** Stick to released versions and check the PGP signature in the release-tag

All code contributions are carefully reviewed by Tobias Brox.  Version tags are signed with PGP.  Of course there is always a risk that someone takes over my PGP key and GitHub access (It's hard to be immune against a [$5 wrench attack](https://xkcd.com/538/)).  The original owner of the repository is still alive and may take over the project again should something happen to me.  I would encourage using AI to do risk assessments.

The library comes with a number of dependencies, one may need to evaluate the security of those too.  The pyproject contains the current list.  Some notes:

* niquests is an optional dependency - you may replace it with requests if you don't trust niquests
* recurring-ical-events and icalendar both have the same maintainer (Nicco Kunzmann).  He is considered trustworthy.
* Tobias now has a policy of moving code not related to CalDAV into separate packages.  Those packages are most of the time either published under the `python-caldav` or `pycalendar` ownership on GitHub, and should be considered to be of the same quality and security level as the CalDAV library.
* No independent security review has been done of the other dependencies - those are all considered to be mature and robust projects.

## Communication dumper debug hook

**Summary:** If someone has the ability to both alter the environment and full read access to /tmp (basically, someone has root access to the computer where the code is run), it will be possible to get access to all communication.  Also, anyone using this debug hook must take responsibility of deleting the dumped files.

**Mitigation:** If this worries you, set `caldav.lib.error.debug_dump_communication=False` after importing caldav.

The following was written when `PYTHON_CALDAV_COMMDUMP` was introduced in v1.4.0:

* An attacker that has access to alter the environment the application is running under may cause a DoS-attack, filling up available disk space with debug logging.
* An attacker that has access to alter the environment the application is running under, and access to read files under /tmp (files being 0600 and owned by the uid the application is running under), will be able to read the communication between the server and the client, communication that may be private and confidential.

Thinking it through three times, I'm not too concerned — if someone has access to alter the environment the process is running under and access to read files run by the uid of the application, then this someone should already be trusted and will probably have the possibility to DoS the system or gather this communication through other means.

As of v3.3 (to be released towards the end of 2026-06), a warning is logged at import time when this variable is set, reminding the operator that request/response bodies and headers (including credentials and calendar PII) are written to uniquely-named files under `/tmp` that accumulate indefinitely.
