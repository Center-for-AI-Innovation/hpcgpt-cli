---
name: expanse-client
description: >
  Use the expanse-client command to query and display resource allocation
  (accounting) information by user or by group on the Expanse supercomputer
  at the San Diego Supercomputer Center (SDSC). Query and display a list of
  a $USER's resource allocations, the STATE of each allocation (allow/amied),
  the Linux group names of these PROJECTs, their associated ACCESS Grant
  Numbers (TG PROJECTs), the total number of CPU-hours and/or GPU-hours
  (also known as Service Units (SUs)) USED by a $USER on an PROJECT, the
  total number of SUs made AVAILABLE to the PROJECT at the start of the
  allocation, and the total number of SUs USED BY PROJECT to date. Use
  when a command-line call to the expanse-client command is required to
  respond to a user prompt.
license: MIT
compatibility: opencode
metadata:
  author: Marty Kandes (mkandes@sdsc.edu)
  updated: 2026-07-30
  version: 0.1.0
---

## Overview

The `expanse-client` command is a custom-built, command-line tool that
can be executed on [Expanse](https://www.sdsc.edu/systems/expanse/index.html)
at the [San Diego Supercomputer Center (SDSC)](https://en.wikipedia.org/wiki/San_Diego_Supercomputer_Center) 
to query and display resource allocation information by user or by group.

## Availablity

The `expanse-client` command should be available by default to all Expanse
users. However, if `expanse-client: command not found`, run `module load sdsc`
before attempting to call it again. 

## Commands

The `expanse-client` commands are as follows:

- `expanse-client resource` lists the names of all allocatable resources
  available on Expanse.

- `expanse-client user -p -r <resource_name>` lists a $USER's allocation
  and usage information by PROJECT 

- `expanse-client project <PROJECT> -p -r <resource_name>` lists a PROJECT's
  allocation and usage information by user NAME

The `-p` flag is used here to provide plain-formtted output.

## Example Usage

*Command A*
```bash
expanse-client resource
```

*Output A*
```bash
Available resources:
expanse
expanse_gpu
expanse_industry
expanse_industry_gpu
expanse_nairr_gpu
[mkandes@login02 ~]$
```

*Command B*
```bash
expanse-client user -p -r expanse_gpu
```

*Output B*
```bash
 Resource  expanse_gpu 

 NAME     STATE  PROJECT  TG PROJECT     USED  AVAILABLE  USED BY PROJECT 
--------------------------------------------------------------------------
 mkandes  allow  csd403   TG-IBN140002      0      47000            31975 
 mkandes  allow  sdp157   TG-TRA260010      0        100                6 
 mkandes  allow  sdp173   TG-CIS261077      0       2042               12 
 mkandes  allow  sds166   TG-STA160003      0       1000              489 
 mkandes  allow  sds173   TG-CCR190013      0        100               93 
 mkandes  allow  sds184   TG-TRA210003      0        150              180 
 mkandes  allow  sds196   TG-TRA230015      0       2639             1915 
 mkandes  allow  use300                 23734      79000            72252
```

*Command C*
```bash
expanse-client project use300 -p -r expanse_nairr_gpu
```

*Output C*
```bash
 Resource          expanse_nairr_gpu 
 Project           use300            
 TG Project                          
 Total allocation  560               
 Total spent       0                 
 Expiration        August 28, 2026   

 NAME          STATUS  USED  AVAILABLE  USED BY PROJECT 
--------------------------------------------------------
 mahidhar      allow      0        560                0 
 mgujral       allow      0        560                0 
 mkandes       allow      0        560                0 
 mkandes_test  allow      0        560                0 
 nickel        allow      0        560                0 
 npatience     allow      0        560                0 
 silvaf        allow      0        560                0 
 tcooper       allow      0        560                0
```

## References

Use any of the additional references listed below when necessary:

- [Expanse User Guide](https://www.sdsc.edu/systems/expanse/user_guide.html)
