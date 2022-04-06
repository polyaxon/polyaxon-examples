[![License: Apache 2](https://img.shields.io/badge/License-apache2-green.svg)](LICENSE)
[![Slack](https://img.shields.io/badge/chat-on%20slack-aadada.svg?logo=slack&longCache=true)](https://polyaxon.com/slack/)
[![Docs](https://img.shields.io/badge/docs-stable-brightgreen.svg?style=flat)](https://polyaxon.com/docs/)
[![GitHub](https://img.shields.io/badge/roadmap-github-blue?style=flat&logo=github&longCache=true)](https://github.com/orgs/polyaxon/projects/5)

# Community

We're opening up this project as a place for our community users to interact with each other and Polyaxon' contributors.

We are also using this project to submit FAQs that we answer multiple times on our slack channel.

We've historically used Slack as the place to ask questions, and we would like to try a new experiment with discussion as the new default place to ask repeatable questions about how to use a specific feature.

This repo also contains our examples as well as examples contributed from other users in the community.

## polyaxon-examples

Code for polyaxon tutorials and examples.

This is the code used for [latest version of Polyaxon](https://polyaxon.com/docs/intro/quick_start/)


This repository contains examples of using Polyaxon with all major Machine Learning and Deep Learning libraries, 
including fastai, torch, sklearn, chainer, caffe, keras, tensorflow, mxnet, and Jupyter notebooks.

If you don't see something you need, Don't hesitate to contact us.

### Examples Structure

This repository has 2 main directories containing examples for running experiments in-cluster, i.e. scheduled and managed by a Polyaxon Deployment, 
as well as experiment running on different platforms and tracked by Polyaxon, i.e. experiments running on laptops, spark, other platforms.

The examples have a comment `# Polyaxon` to show what is added to a raw code to enable the lightweight Polyaxon integration.

### Getting Started

If you are new to Polyaxon we recommend reading our [quick-start](https://polyaxon.com/docs/intro/quick-start/) guide which explains some of the core Platform capabilities.

### Setup & Installation

Please check our [documentation](https://polyaxon.com/docs/) to learn about how to deploy Polyaxon.

All examples (in-cluster and on other examples running on other platforms) require our library `pip instal polyaxon` to track and add instrumentation to the experiments.
 
### in-cluster Examples

In order to run these examples, you need to deploy a Polyaxon with a scheduling component enabled.

### Tracking Examples

These examples should can run outside of a Polyaxon cluster.

## discussions
Discussions as a place to answer frequently asked questions and to organize community users interaction.

## Q&A, Ideation, and feature requests

This is a great place to:

- Ask questions about Polyaxon
- Request features from our team
- Share ideas and projects you are working on

## Bug Reports

If you've found a bug, it is best to file an issue. If the issue is repeatable we will re-share it as an FAQ discussions.

## Join us on Slack

You are welcome to join our Slack community by signing up [here](https://polyaxon.com/slack/)

We will still be using Slack as a place to provide private help and make announcements about events and releases. We encourage all of our users to still join our community. If you have a question that contains sensitive information that needs to be asked in private, it is best to do it on Slack.

## Code of Conduct

In addition to the [Code of Conduct](CODE_OF_CONDUCT.md) guide line, we have a couple of rules we would like you to follow:
 * Be nice, always!
 * Be respectful; we assume positive intent from you and we ask the same in return
 * Avoid posting sensitive information
 * Don’t abuse tagging other users
 * Don’t advertise material unrelated to Polyaxon
 * Explicit is better than implicit: be as precise as you can.
 * It’s OK to disagree but disagree politely and constructively.
    * Avoid absolutes: absolute statements do not provide room for a conversation to grow
    * Never attack: being defensive about your own ideas, or running offense on another person’s ideas will always result in shutting down collaboration
    * Stay humble: disagreements are learning opportunities
 * Before creating a new topic, search if someone posted a similar issue before to avoid duplication.
 * Each topic should be well-scoped (focused on one thing), non-duplicated and specific to problematic we are solving in one of our repos or with our solution.


## Organizing FAQs and discussions

 * Title: try to specify the problem rather than the feature or solution you tried.
 * If you have multiple issues, please break them down to multiple discussions.
 * Use labels to categorize the new discussion.
 * Provide as much information as you can to help us identify the root cause of the issue:
   * What environment are you using, e.g. Python version when for CLI/Library issues?
   * What infrastructure are you using, e.g. an on-premise deployment, a specific cloud provider (AWS, GCP, Azure).
   * What version are you using?
   * Did you check the docs and search bar?
   * Did you check the discussions and github search?
   * Did you try upgrading before asking?
   * If the issue is related to operations on k8s, can you please use the inpsection button and copy/paste the YAML results as an attachement (you can replace sensitive info with `xxx`).
   * Can you share logs or code snippets that can make it easier to reproduce your issue?
 * As a discussion creator, you will have a button that allows you to accept an answer. If some user responds to your question with a great answer, mark it as the accepted solution. Doing that helps others quickly navigate to the answer that helped you solve the problem.

## Categories

 * **Announcements**: a category for general-purpose category for announcing new releases and blog posts.
 * **FAQ**: a category for frequently asked questions not strictly falling into any other mentioned category.
 * **Q&A**: a category to ask for help.
 * **General**: a category for discussing anything related to Polyaxon.
 * **Show and tell**: a category for links to various resources that can help you get started and learn about Polyaxon as we as a place for sharing blog posts, walkthroughs, or simply sharing how to solve a specific problem.
 * **Ideas**: a category to share ideas for new features.

## Labels

You can use labels to further categories new discussions, here are some helpful labels:
 * experimenation: jobs, tracking, visualizations, dashboards, logs, cli
 * automation: orchestrating, scheduling, hyperparameter tuning, DAGs, mapping, dependency management, events, actions, hooks, triggers, backfills
 * termination: retries, restarts
 * setup
 * CI/CD 
 * environments (development, staging, production, etc.)
 * integrations
 * ui
