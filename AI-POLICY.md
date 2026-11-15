# Policy on usage of Artificial Intelligence and other tools

## Read this first

The most important rule: be honest and inform about it!  The
second-most important rule: YOU should add value to the project.  That
value may be to find and reproduce a bug and verify that an
AI-generated fix solves the issue.

If you ask the AI to "find some low-hanging fruit in the issue tracker
and generate a PR", then you're not adding value to the project.  The
maintainer can probably do that himself, with a better overview of
what needs to be prioritized.  Reviewing an AI-generated PR often
takes the maintainer more effort than doing the work directly.

Keep a log of the prompts and/or commands used - this should be
included verbatim in the git commits as long as it's possible
without making the messages too messy.  When relevant, chat-output may
also need to be included or paraphrased.  The `docs/design`-folder can
be used for dumping AI-generated design documents, code reviews,
prompts that are too large for being included in the commit message,
etc.

If you think the rest of the document is too long to read, at least
ask the AI to ensure the policy is followed.  "YOU" in this
document means the human, not the AI.

## NLnet funding and its GenAI policy

This project receives funding from [NLnet](https://nlnet.nl/), and has
done so since before NLnet introduced a GenAI policy.  The project is
currently committed to [version
1.1](https://nlnet.nl/foundation/policies/generativeAI/1.1/) of that
policy, which allows GenAI-assisted work as long as it is disclosed and
logged, and this document is written to fit it.  [Version
2.0](https://nlnet.nl/foundation/policies/generativeAI/2.0/) of
2026-10-20 only allows GenAI to be used in a read-only manner (code
review, for instance), and NLnet wants it adopted.  This document will
have to be revised if the project continues to receive NLnet funding.
Until that is settled, the rules below apply to all contributions.

The priority is to deliver a good, feature-complete, easy-to-use and
bug-free library that stays compatible with as many servers as possible.
NLnet funding makes it possible for me to prioritize this, and spend
some hours a week rather than some hours a month on this project.
However, as the AI-models keep improving it may be questioned whether a
few hours a month of unfunded "vibe engineering" is of higher
value than a few hours a week of funded manual human labour.

## Transparency matters

If you've spent hours, perhaps a full day of your time writing up a
pull request, then I sort of owe you something.  I should spend some
of my time looking through the submission carefully, and if nothing
else, I owe to be polite, respectful and guide you in the right
direction or give a good explanation for why I think your pull request
is pulling the project in the wrong direction.  A human being have
feelings, I should be careful not to hurt your feelings.

At the other hand, perhaps you've spent 30 seconds either doing `ruff
check --fix ; gh pr create` or telling Claude "Please fix support for
Microsoft Exchange and create a pull request".  Do I still owe you to
spend time looking through the submission carefully and spending time
being polite and caring about your feelings?

Perhaps your pull request is just one out of many such "drive-by pull
requests".  It doesn't scale for a maintainer to spent lots of time on
each such pull request.  At least, I should not waste time trying to
explain in details why I'm rejecting the pull request.

## Bugfixes are (most often) welcome

It's fine to ask the AI for help to analyze a bug and create a fix for
it.  By discovering the bug, reproducing it and testing it you're
adding real value to the project even when you don't understand what
the AI did to fix it - **just remember to be honest and transparent about it**.

## General rules

* **It's always a good idea to use the AI for code reviews**.  It
  seems that by late 2026, the good AI-models are better than humans
  on doing code reviews, and the more "eyeballs" (even virtual ones)
  the merrier.  One would assume an AI-model to generate code that the
  same AI-model wouldn't easily find problems with the code it has
  just generated, but at least with Claude Opus, I frequently find
  that asking Opus to do a "clean context review" of the code Opus
  just created, it finds lots of problems!

* Do **respect the maintainers time**.  If/when the maintainer gets
  overwhelmed by pull requests of questionable quality or pull
  requests that do not pull the project in the right direction, then
  it will be needed to add more requirements to the Contributors
  Guidelines.

* **YOU should add value to the project**. If you prompt the AI to
  "look through the issues for this project, find some
  low-hanging-fruit, fix the issue and send a PR", then it's the AI
  and not you delivering value.  I can run the same prompt myself, and
  it would cost me less effort than to review your contribution.

* **YOU ought to understand the changes**.  The change
  goes into the project attributed to your name (or at least github
  handle), so it would be nice if you understand the change you're
  proposing.

* **Transparency** is important.  Ok, it's said two times further up
  already, but it's important.  If a significant part of the value in
  the pull request was generated by tools, then it's relevant.  Do not
  write "I found this issue and here is a fix", but rather "I ran the
  (ruff tool, code review by Claude Mythos, etc) on the code, it found
  this issue, and here is the fix it made".  If the AI was fixing a bug for
  you, then write in the pull request that "this bugfix was vibed up,
  I have no idea what the AI has done here".  End the commit message
  with "Assisted-By: ..." ("Co-Authored-By: ..." is deprecated).

* **YOU** should be ready to follow up and respond to feedback and
  questions on the contribution.  If you're letting the AI do this for
  you on your behalf, then it's a chance you're neither honest nor
  adding value to the project.  You should at least do a quick QA on
  the AI-answer and acknowledge that it was generated by the AI.

* Most AI policies warns about potential copyright infringements.  I
  can hardly think it's any risk wrg of contributions to the Python
  CalDAV library.  In particular, if your changeset consists of lots
  of minor changes to existing code, then it's nothing to worry about.

* It's a good idea to generate tests first, verify that they are
  breaking, and then generate the code.  When using AI, it's also
  easy, so any AI-generated contributions ought to follow this policy.

* The Contributors Guidelines aren't strongly enforced on this project
  as of 2026-02, and I can hardly see cases where the AI would break
  the Code of Conduct, but at the end of the day, it's **YOUR**
  responsibility that the contribution follows those guidelines.

## Disclosure of GenAI usage

The maintainer started playing with Claude Code in the end of 2025 - and [blogged about it](https://www.redpill-linpro.com/techblog/2026/03/20/from-luddite-to-vibe-coder.html)

Since 2.2.6, development has been heavily assisted by Claude - which is pretty obvious when looking into the commit messages.  My experiences have been mixed - sometimes it seems to be doing a better and faster job than me, other times it seems to be making a mess a lot faster than what I can do it.  Despite (or because of?) using Claude extensively, I spent much more time on the 3.0.0-release than estimated.  However, the models are getting better, and my understanding of how to make the best out of it is also growing.

As for the 3.0.0-release, lots of time and efforts have been spent on doing QA on the changes, fixing up things and/or asking Claude to do a better job.  The surge of issues reported after the 3.0-release is probably unrelated to the AI usage - it's a result of trying to shoehorn both async and API changes into it without breaking backward compatibility and without duplicating too much code.  The CHANGELOG.md entry for 3.0 explicitly declared a caveat: "there are massive code changes in version 3.0, so if you're using the Python CalDAV client library in some sharp production environment, I would recommend to wait for two months before upgrading".

Before I started to use the AI, I was aiming for "logical" commits containing independent, self-sustained changesets.  I've more or less given up squashing commits and keeping a linear history, now a "change" (pull request on GitHub) more often than not contains multiple commits tied together by a merge-commit.

## Future plans of GenAI-usage

I do want to go back to the old ways for doing the "core development tasks" - new features and complex refactoring.  If nothing else, it's important for maintaining my brain cells, coding skills and making sure all the changes stick to my memory.  The new policy is that GenAI-tools should be used mainly for improving quality, not speeding up the development.  However, as my brain apparently has continued rotting due to extensive AI-usage, combined with improved models, I haven't been able to get back to "the old ways".

GenAI is very well suited for certain tasks, particularly anything that is either "mundane and tedious" or unrelated to "the working end" of the library.  Examples:

* Code reviews!  I now have a policy that all changesets and releases should go through AI-driven code review.  By itself it sounds like a good idea, though one should be aware of the risk that this comes *instead* of human reviews rather than as an addition.  (Perhaps I need to tweak my prompts/workflows a bit - it seems that if looping through "do code review", "fix code review issues", eventually it will rather hallucinate up issues than coming up with the conclusion "no issues found").
* Writing up test code.  I do believe "test driven development" is a good idea (write test code first, then the logic), but writing tests may be both tedious and difficult.  Claude can make them really fast, though it still needs some QA, care should be taken to ensure it's testing the right thing.
* Debugging.  It's easy to get stuck and spend tons of time on debugging - sometimes (but not always) Claude can find them easily.  (Best approach may sometimes be to do manual debugging in parallel with AI-driven debugging ... sometimes I "win", other times [Claude Sonnet 4.5] "wins".  Edit: Opus 5.5 almost always wins).
* Minor bugfixes ... the bugfix itself may be a one line changeset, but tests and debugging take time.
* Maintaining the integration test framework.  I've consistently failed setting up and maintaining a "battery" of caldav servers from 2013 to 2025, thanks to Claude we now have it in place.  It's important, a majority of issues reported are about compatibility problems, the more servers I have for testing every release, the fewer troubles will be discovered downstream.
* Setting up CI-related automated QA tests, pipelines etc
* The companion caldav-server-tester tool is quite suitable for GenAI-work - it's a bit like test code, writing up the checks to discover various server issues is rather tedious and time-consuming.  This tool has grown a lot in 2026 thanks to Claude.
* Investigations of different architectural choices - like with the async work I had Claude develop different design approaches and chose the one that I felt most comfortable with (though I'm still not sure that I did the right choice).
* Reading RFCs and quickly giving a pointer to the relevant sections, or verifying that the code is according to the standards or not (but care should be taken - I've seen Claude hallucinating completely wrong RFC references).
* Various other mundane and tedious work (e.g. "I left a TODO-note in the code over there, could you have a look at it and eliminate it?").
