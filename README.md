[![License: Apache 2](https://img.shields.io/badge/License-apache2-green.svg)](LICENSE)
[![Slack](https://img.shields.io/badge/chat-on%20slack-aadada.svg?logo=slack&longCache=true)](https://polyaxon.com/slack/)

> N.B. This is a read-only repo, you can create issues or PRs in the [main repo](https://github.com/polyaxon/polyaxon/issues).

# polyaxon-examples

Code for polyaxon tutorials and examples.

This is the code used for [latest version of Polyaxon](https://docs.polyaxon.com/concepts/quick_start/)


This repository contains examples of using Polyaxon with all major Machine Learning and Deep Learning libraries, 
including fastai, torch, sklearn, chainer, caffe, keras, tensorflow, mxnet, and Jupyter notebooks.

If you don't see something you need, Don't hesitate to contact us.

## Examples Structure

This repository has 2 main directories containing examples for running experiments in-cluster, i.e. scheduled and managed by a Polyaxon Deployment, 
as well as experiment running on different platforms and tracked by Polyaxon, i.e. experiments running on laptops, spark, other platforms.

The examples have a comment `# Polyaxon` to show what is added to a raw code to enable the lightweight Polyaxon integration.

### Getting Started

If you are new to Polyaxon we recommend reading our [quick-start](https://docs.polyaxon.com/concepts/quick-start/) guide which explains some of the core Platform capabilities.

### Setup & Installation

Please check our [documentation](https://docs.polyaxon.com) to learn about how to deploy Polyaxon.

All examples (in-cluster and on other examples running on other platforms) require our [client](https://github.com/polyaxon/polyaxon-client) to track and add instrumentation to the experiments.
 
### in-cluster Examples

In order to run these examples, you need to deploy a Polyaxon with a scheduling component enabled.

### Tracking Examples

These examples should can run outside of a Polyaxon cluster.
