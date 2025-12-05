# Security policy

Issues should be fixed ASAP, and information on any security issue should be published as soon as it's fixed. Use the GitHub issue tracker or check up [CONTACT](CONTACT.md) or even the [CODE OF CONDUCT](CODE_OF_CONDUCT) file to get in touch with the maintainer.

There are no "LTS"-releases of the CalDAV package, but the maintainer will always consider backporting security fixes if it's deemed relevant.  The maintainer is doing most of the maintenance on hobby-basis and may have other things in life preventing him from dealing with issues on the go, so no guarantees are given.

All contributions are carefully reviewed by the maintainer, and all releases are carefully tested and tagged with a PGP-signed commit.

# Known security issues and risks

## RFC6764

I do see a major security flaw with the RFC6764 discovery. If the DNS is not to be trusted, someone can highjack the connection by spoofing the service records, and also spoofing the TLS setting, encouraging the client to connect over plain-text HTTP without certificate validation. Utilizing this it may be possible to steal the credentials. This flaw can be mitigated by using DNSSEC, but DNSSEC is not widely used, and fixing support for DNSSEC validation in the CalDAV library was found to be non-trivial (perhaps I'll look into it again some time after 3.0 has been released).  This has been mitigated by adding a require_tls` connection parameter that is True by default, plus by ensuring one isn't routed to a different domain.

## DDoS/OOM risk

The package offers both client-side and server-side expansion of recurring events and tasks.  It currently does not offer expansion for open-ended date searches - but with a large enough timespan and a frequent enough RRULE, there may be millions of recurrences returned.  Those recurrences are returned as a generator, so things will not break down immediately.  However, there is no guaranteed sort order of the recurrences ... and once you add sorting parameters to the search, bad things may happen.

## Bugs causing weird things happening

Weird things may happen due to bugs both on in the CalDAV package, on your side and on the server side.  Here are some weird experiences with Zimbra:

* I have experiences that cancelling participation in an event caused the event to be cancelled for all participants (even if the person deciding to not go to the event was not an organizer and should have no permissions to edit the event).  Clearly a server-side issue.
* I once tried to restore from backup and push ten years of ical code to the calendar server.  The calendar server responded by re-inviting people to the meetings we had ten years ago.  I'm inclined to call that also a server side bug.
* Many other things may happen.

## Malicious usage

Beware of risks and exposure when creating applications:

* Your code may handle username and password, be careful not to expose such credentials.  Even the URL to the calendar server and/or calendar may be something people want to keep private.
* Consider that calendar events and such is personal data, which deserves protection.  In the EU with the GDPR, such protection is even mandated by law.
* If you allow arbitrary people to create calendar content to be saved to a server, there may be some risks involved:
  * Depending on the server implementation, it may be possible to use the caldav library for sending spam emails.
  * Be aware of DoS-attacks: By storing too much / too big / specially crafted icalendar data, the server and/or client may crash or consume all available resources.
  * If allowing anonymous parties to save and retrieve data from your server, you may end up with responsibility for spreading illicit information.  This may include things like child porn.  Political or religious propaganda may be legitimate and legal in some countries, but may involve death penalty in other countries.  Your calendar server may also be used for coordinating criminal activity.
* If you allow arbitrary people to fetch calendar content from the server, there may also be some risks involved - in particular, a DoS-attack by requesting a large time span of expanded events.

## Malicious code

All code contributions are carefully reviewed by Tobias Brox.  Version tags are signed with PGP.  Of course there is always a risk that someone takes over my PGP key and github access (It's hard to be immune against a  [5$ wrench attack](https://xkcd.com/538/)).  The original owner of the repository is still alive and may take over the project again should something happen to me.  I would anyway encourage using AI to do risk assessments.

The library comes with a number of dependencies, one may need to evaluate the security of those too.  The pyproject contains the current list.  Some notes:

* niquests is an optional dependency - you may replace it with requests if you don't trust niquests
* recurring-ical-events and icalendar both has the same maintainer (Nicco Kunzmann).  He is considered trustworthy.
* Tobias now has a policy of moving code not related to CalDAV into separate packages.  Packages under the `python-caldav` ownership on GitHub should be considered to be of the same quality and security level as the CalDAV library.
* No security review have been done of the other dependencies.
