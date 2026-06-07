# eval_questions Review

For each pair: review the drafted `eval_question`, edit in the JSONL file as needed,
then set `"approved": true` in `eval_questions.jsonl`.

**Columns:** ID | Title | Raw question body | Drafted eval_question | Flags | Approved

---

## auth0/node-jsonwebtoken/issue/957
**Title:** Signature generation fails for SM2 private keys with ES256 algorithm for node 18 version
**Repo:** auth0/node-jsonwebtoken | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Description

`jwt.sign(<payload>, <utf8 encoded SM2 private key>, { algorithm: 'ES256' })` fails with `"error":{"code":"ERR_OSSL_INVALID_DIGEST","library":"Provider routines","reason":"invalid digest"}`  when using node 18.17.0.

The above command works fine with node version 16 but fails with node versions 18 and 20.

### Environment

- **Version of this library used:** jsonwebtoken 9.0.0  and 9.0.2
- **Version of the platform or framework used:** nodejs 18.17.0

```

### Drafted eval_question
```
Why does `jwt.sign(<payload>, <utf8 encoded SM2 private key>, { algorithm: 'ES256' })` fail with the error code 'ERR_OSSL_INVALID_DIGEST' when using node 18.17.0, while it works with node version 16? This issue occurs with jsonwebtoken versions 9.0.0 and 9.0.2.
```

**Flags:** Reporter cited: ['9.0.0', '9.0.2', '18.17.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## auth0/node-jsonwebtoken/issue/921
**Title:** Security Vuln In Semver Dependency
**Repo:** auth0/node-jsonwebtoken | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
├─┬ jsonwebtoken@9.0.1
│ └── semver@7.3.8 deduped

CVE-2022-25883 (OSSINDEX) 




Versions of the package semver before 7.5.2 are vulnerable to Regular Expression Denial of Service (ReDoS) via the function new Range, when untrusted user data is provided as a range.

CWE-1333 Inefficient Regular Expression Complexity

CVSSv3:

Base Score: HIGH (7.5)
Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H


References:

OSSINDEX - [[CVE-2022-25883] CWE-1333](https://ossindex.sonatype.org/vulnerability/CVE-2022-25883?component-type=npm&component-name=semver&utm_source=dependency-check&utm_medium=integration&utm_content=8.3.1)
OSSIndex - http://web.nvd.nist.gov/view/vuln/detail?vulnId=CVE-2022-25883
OSSIndex - https://github.com/npm/node-semver/pull/564
OSSIndex - https://vuldb.com/?id.232060




Vulnerable Software & Versions (OSSINDEX):

cpe:2.3:a:*:semver:7.3.8:*:*:*:*:*:*:*
```

### Drafted eval_question
```
I am using jsonwebtoken@9.0.1, which depends on semver@7.3.8. I found that versions of semver before 7.5.2 are vulnerable to Regular Expression Denial of Service (ReDoS) via the function new Range when untrusted user data is provided as a range. This is identified as CVE-2022-25883 with a CVSSv3 base score of 7.5. Is this a genuine security vulnerability in my usage of jsonwebtoken, and how should I address it?
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2022-25883'] | NEEDS REVIEW | Reporter cited: ['CVE-2022-25883', 'CWE-1333', '7.3.8', '7.5.2']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## auth0/node-jsonwebtoken/issue/914
**Title:** please publish a new NPM package
**Repo:** auth0/node-jsonwebtoken | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
Please also address

## CVE-2022-25883 - Medium Severity Vulnerability
<details>

<p></p>
<p>Library home page: <a href="https://registry.npmjs.org/semver/-/semver-7.5.0.tgz">https://registry.npmjs.org/semver/-/semver-7.5.0.tgz</a></p>
<p>

Dependency Hierarchy:
    - jsonwebtoken-9.0.0.tgz
      - :x: **semver-7.5.0.tgz** (Vulnerable Library)
<p>Found in base branch: <b>master</b></p>
</p>
</details>
<p></p>
<details><summary><img src='https://whitesource-resources.whitesourcesoftware.com/medium_vul.png?' width=19 height=20> Vulnerability Details</summary>
<p>  
  
Versions of the package semver before 7.5.2 are vulnerable to Regular Expression Denial of Service (ReDoS) via the function new Range, when untrusted user data is provided as a range.



<p>Publish Date: 2023-06-21
<p>URL: <a href=https://www.mend.io/vulnerability-database/CVE-2022-25883>CVE-2022-25883</a></p>
</p>
</details>
<p></p>
<details><summary><img src='https://whitesource-resources.white...
```

### Drafted eval_question
```
Could you release a new NPM package for the auth0/node-jsonwebtoken library that includes the latest commit allowing the decode method to be stubbed? Additionally, there is a need to update the package to address a vulnerability related to the semver dependency. Specifically, CVE-2022-25883 affects versions of semver before 7.5.2, which are vulnerable to Regular Expression Denial of Service (ReDoS) via the function new Range when untrusted user data is provided as a range. Could you ensure that the updated package addresses this vulnerability by upgrading semver to version 7.5.2 or later?
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2022-25883'] | NEEDS REVIEW | Reporter cited: ['CVE-2022-25883', 'semver-7.5.0', 'semver-7.5.2']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## auth0/node-jsonwebtoken/issue/739
**Title:** error:04075070:rsa routines:RSA_sign:digest too big for rsa key
**Repo:** auth0/node-jsonwebtoken | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
Hmmm so I can make sure I understand (as I don't know anything about cryptography), what is the relation (if any) between the algorithm (RS512, RS256) I would choose and the modulus length ?

I can sign my token with, say, the RS256 algorithm and a modulus of 2048, if I wanted ? That is, they don't need to match

```

### Drafted eval_question
```
I am using the auth0/node-jsonwebtoken library version 8.5.1 on Node in Windows. When I attempt to sign a token using the RS512 algorithm, I encounter the error: `error:04075070:rsa routines:RSA_sign:digest too big for rsa key`. This error also occurs when using RS256. Here is the code I am using:

```
const jwt = require("jsonwebtoken");

const token = jwt.sign({ sub: 1 }, "...", { expiresIn: '7d', algorithm: "RS512" });
```

Another user reported the same issue on Node 15, Ubuntu, using a random private key:

```
-----BEGIN RSA PRIVATE KEY-----
MIIBOgIBAAJBAKrNEPQdc2yJURauXDa2Yu2KLj6sHkM3EDMWrHEC/4RKdrMt9qFl
Hm11YoQRYIm2v/mtdBjrg+FD+MnaEtChYFkCAwEAAQJAX2YsqvzsJFpKVW3MCa8z
cFP24oCGYqqVvMNUS8cN6tgzm5XBZIuc7c2NQ+XzG7xGmvkklbTtKGCkBlrJHJ8L
AQIhAPfjw4kaK1RPga10Cc/+s4QGIRJUPsICBwVY2fFUDMk5AiEAsGOil+vUDr35
yMKod0NwCbUubukGHX/x6fxyY38G8CECIFtjM7Y62JiHizZIHkn5C3Nz0wNv3Ycm
ujHldMu8gc45AiEAg+6SP+WxoDEycpo+na4AUBKHn4eF/myjiis7d/YcP2ECIFnv
bdO+HrfCgkAcbMw0d2pEisYXfZWkAW8q9NJ4OyMp
-----END RSA PRIVATE KEY-----
```

This yields the same error. Is this behavior a genuine issue with the node-jsonwebtoken library or a bug in Node.js? What is the relationship between the algorithm (RS512, RS256) and the modulus length of the RSA key?
```

**Flags:** Reporter cited: ['8.5.1']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## auth0/node-jsonwebtoken/issue/728
**Title:** Use a default of `["HS256"]` for `verify` to be in sync with default for `sign`
**Repo:** auth0/node-jsonwebtoken | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
By default `sign` uses `options.algorithm: "HS256"`.

In contrast `verify` does not use `options.algorithms: ["HS256"]` by default - but instead accepts all algorithms.

This means by default we sign with HS256 but we verify and accept all algorithms - for example also the `none` algorithm.

If we're setting a default in sign we should set the same default in verify - and keep them in sync.

Thoughts?
```

### Drafted eval_question
```
In the auth0/node-jsonwebtoken library, the `sign` function defaults to using the `HS256` algorithm, but the `verify` function does not default to any specific algorithm and instead accepts all algorithms, including `none`. This means a token signed with `none` can be verified without explicitly allowing `none` as an algorithm. Here is an example:

```js
> jwt.sign({ user: 42 }, undefined, { algorithm: 'none' });
'eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJ1c2VyIjo0MiwiaWF0IjoxNTkzNDM2NTEyfQ.'
```

The key is not needed - I set it to undefined.

By default now we can verify that token without having to explicitly allow none as an algorithm:

```js
> jwt.verify('eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJ1c2VyIjo0MiwiaWF0IjoxNTkzNDM2NTEyfQ.')
{ user: 42, iat: 1593436512 }
```

and also works in this scenario when we accidentally pass undefined (or anything else false-y as an argument):

```js
> jwt.verify('eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJ1c2VyIjo0MiwiaWF0IjoxNTkzNDM2NTEyfQ.', process.env.MYKEY) // oops env var undefined
{ user: 42, iat: 1593436512 }
```

Shouldn't the `verify` function have a default algorithm setting similar to `sign` to prevent this behavior? Shouldn't users be required to explicitly pass `algorithms: ["none"]` if they intend to allow tokens signed with `none`?
```

**Flags:** Reporter cited: ['v8.5.1']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## auth0/node-jsonwebtoken/issue/711
**Title:** RFC confrontation on "none" algo
**Repo:** auth0/node-jsonwebtoken | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
https://github.com/auth0/node-jsonwebtoken/blob/5f10bf9957a2541828501cfecab0310908b2f62f/verify.js#L109-L111

so it's intentional?
```

### Drafted eval_question
```
In the auth0/node-jsonwebtoken library, when using the 'none' algorithm, the RFC 7518 specifies that such objects must not be accepted as valid unless explicitly allowed. However, the current behavior allows verification without specifying this. Should there be an option to enforce this requirement, and is the current implementation intentional? Here is a reproduction of the issue:

```javascript
> var token = jwt.sign({'a':1}, 'asdf', { algorithm: 'none'})
undefined
> jwt.verify(token)
{ a: 1, iat: 1587359376 }
```

Expected behavior would be:

```javascript
> var token = jwt.sign({'a':1}, 'asdf', { algorithm: 'none'})
undefined
> jwt.verify(token)
throws error
> jwt.verify(token, '', { algorithm: 'none'})
{ a: 1, iat: 1587359376 }
```
```

**Flags:** Reporter cited: ['5f10bf9957a2541828501cfecab0310908b2f62f']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## auth0/node-jsonwebtoken/issue/706
**Title:** Less Secure (jwt token decodes without any secret)
**Repo:** auth0/node-jsonwebtoken | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Team JWT,  I have created a token using jwt.sign where I have passed my own secret and then I copied the token pasted it on jwt.io website and I was amazed it decodes my token without any secret 
 and showing usernames and passwords.

Here Is the toke for Demo purpose: ```eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2Vybm1hZSI6InNzYXR5YW1jaGF1aGFuIiwicGFzc3dvcmQiOiJ3aHlpdGlzbWUiLCJpYXQiOjE1ODUxMzM0ODMsImV4cCI6MTU4NTM5MjY4M30.bKtmn03-ZnAAzNxnNk9ZPlrsbbk8lUThMt24gwL-r2w```
I just wanted to know is this secure to do token-based authentication in a web app.
#### Hoping for the quick response.

```

### Drafted eval_question
```
I created a JWT token using jwt.sign with my own secret. When I pasted the token on jwt.io, it decoded without requiring any secret and displayed usernames and passwords. Here is the token for demonstration: ```eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2Vybm5hbWUiOiJzc2F0eWFtY2hhdWhhbiIsInBhc3N3b3JkIjoid2h5aXRpc21lIiwiaWF0IjoxNTg1MTMzNDgzLCJleHAiOjE1ODUzOTI2ODN9.bKtmn03-ZnAAzNxnNk9ZPlrsbbk8lUThMt24gwL-r2w``` Is it secure to use token-based authentication in a web app?
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## auth0/node-jsonwebtoken/issue/665
**Title:** Add option to ignore signature validation (e. g. for dev/test purposes)
**Repo:** auth0/node-jsonwebtoken | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Describe the problem you'd like to have solved

> In dev and test environments it may be feasible to work with a test JWT token which has no valid signature, e. g. for cases where the token provider can not be modified to create tokens in a manner how a relying party needs it for a special edge situation. In this case the JWT payload could be modified manually be the developer to match/test the requirement, but the current jsonwebtoken implementation does not allow to use this invalid token within ```jwt.verify()``` function.

### Describe the ideal solution

> Adding a new option ```ignoreSignature``` to the existing set of options (like ```ignoreExpiration``` and ```ignoreNotBefore```) would allow developers to use self-modified tokens for tests but still having checks for proper ```issuer```, ```subject```, ```audience``` in place.

## Alternatives and current work-arounds

> Using of ```jwt.decode()``` instead of ```jwt.verify()``` helps in at least getting the JWT de...
```

### Drafted eval_question
```
In development and test environments, it may be necessary to work with a test JWT token that lacks a valid signature, especially in cases where the token provider cannot be modified to create tokens as needed for specific edge cases. The current jsonwebtoken implementation does not allow the use of such invalid tokens with the `jwt.verify()` function. Would it be possible to add an `ignoreSignature` option to the existing set of options (like `ignoreExpiration` and `ignoreNotBefore`) to allow developers to use self-modified tokens for tests while still performing checks for `issuer`, `subject`, and `audience`?
```

**Flags:** Reporter cited: ['a6235fa561b5c30884c97ea0b30c3db3b546ae2c']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## auth0/node-jsonwebtoken/issue/656
**Title:** Token Destroy Method
**Repo:** auth0/node-jsonwebtoken | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
I want to know about that why jsonwebtoken package does not provide destroy method to kill the token. I am getting stuck to find out the solution How to set expire time to 0 or current time while logout in NodeJSapp?
Please give me the proper solution for that.
```

### Drafted eval_question
```
Why does the jsonwebtoken package not provide a destroy method to invalidate a token? How can I set the token's expiration time to 0 or the current time upon logout in a Node.js application?
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/10731
**Title:** Security warnings reported for axios 1.15.0 dependency chain
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Hi team 👋,
Just wanted to flag that our security scan reported a few warnings related to axios 1.15.0.

CVE-2025-62718 (High severity, CVSS 7.8) affecting axios
follow-redirects@1.15.11 (Medium severity, CVSS 6.9) pulled in as a transitive dependency
-> Scanner suggests upgrading to 1.16.0

Could you let us know if there’s a recommended axios version that already addresses this, or if a dependency update is planned?
Thanks a lot!
```

### Drafted eval_question
```
Our security scan reported warnings related to axios 1.15.0, specifically CVE-2025-62718 (High severity, CVSS 7.8) affecting axios and a Medium severity issue with follow-redirects@1.15.11 as a transitive dependency. The scanner suggests upgrading to 1.16.0. Is there a recommended version of axios that addresses these issues, or is a dependency update planned?
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2025-62718', 'fixed_versions:1.15.0'] | NEEDS REVIEW | Reporter cited: ['CVE-2025-62718', 'follow-redirects@1.15.11']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/10707
**Title:** Vulnerabilities still flagged in v0.31.0 after update (SSRF, DoS, Metadata Exfiltration)
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
axios  <=1.14.0
Severity: critical
Axios is Vulnerable to Denial of Service via __proto__ Key in mergeConfig - https://github.com/advisories/GHSA-43fc-jf86-j433
Axios has a NO_PROXY Hostname Normalization Bypass Leads to SSRF - https://github.com/advisories/GHSA-3p68-rc4w-qgx5
Axios has Unrestricted Cloud Metadata Exfiltration via Header Injection Chain - https://github.com/advisories/GHSA-fvcv-3m26-pcqx

I assume that after upgrading the version to 0.31.0 ( which has a backport of the changes from the 1.x branch), we should no longer have any critical vulnerabilities, but it seems that it is not working.

https://github.com/axios/axios/releases/tag/v0.31.0

Is there an extra configuration step or a specific "report update" we need to trigger for scanners to recognize this version as safe?

@jasonsaayman – Is there any known reason scanners would still be flagging 0.31.0 as vulnerable to these specific CVEs?


```

### Drafted eval_question
```
After upgrading to axios version 0.31.0, which includes backported changes from the 1.x branch, I expected that critical vulnerabilities such as Denial of Service via __proto__ Key in mergeConfig, NO_PROXY Hostname Normalization Bypass leading to SSRF, and Unrestricted Cloud Metadata Exfiltration via Header Injection Chain would be resolved. However, security scanners are still flagging version 0.31.0 as vulnerable to these issues. Is there an extra configuration step or a specific 'report update' needed for scanners to recognize this version as safe? Is there any known reason why scanners would still flag 0.31.0 as vulnerable to these specific CVEs?
```

**Flags:** LEAK FLAGS: ['fixed_versions:0.31.0'] | NEEDS REVIEW | Reporter cited: ['GHSA-43fc-jf86-j433', 'GHSA-3p68-rc4w-qgx5', 'GHSA-fvcv-3m26-pcqx', '0.31.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/10685
**Title:** [Security] Backport SSRF vulnerability fix (CVE-2025-62718) to 0.x branch
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
# Backport Request: SSRF Vulnerability (CVE-2025-62718) to 0.x branch

## Description

A Server-Side Request Forgery (SSRF) vulnerability has been identified in axios, assigned CVE-2025-62718. This vulnerability has been fixed in the 1.x branch but is still present in the 0.x branch, which is still widely used.

## Request

I kindly request consideration for backporting the fix for this vulnerability to the 0.x branch to ensure the security of users still relying on this version.

## Rationale

1. Security: SSRF vulnerabilities can lead to severe security issues, allowing attackers to make unauthorized requests from the server.
2. Legacy Version Support: Many projects still use the 0.x branch and may not be ready to upgrade to 1.x for various reasons.
3. Security Compliance: Backporting this fix will help projects using 0.x meet security requirements.

## Additional Information

- CVE: CVE-2025-62718
- Fixed in branch: 1.15.0
- Backport needed to: 0.x

Thank you for considering this re...
```

### Drafted eval_question
```
Is it possible to backport the fix for the Server-Side Request Forgery (SSRF) vulnerability identified as CVE-2025-62718 from the 1.x branch to the 0.x branch of axios? This vulnerability has been fixed in version 1.15.0, but many projects still rely on the 0.x branch and may not be ready to upgrade. Backporting the fix would help ensure security compliance and protect users from potential unauthorized requests made from the server.
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2025-62718'] | NEEDS REVIEW | Reporter cited: ['CVE-2025-62718', '1.15.0', '0.x']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/10643
**Title:** Which Axios versions were affected and which version is safe to use?
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Hi

I recently saw reports that some versions of Axios were compromised and contained malicious code, so I want to clarify before using it in my project.

From what I understand, the affected versions were:

* axios@1.14.1
* axios@0.30.4

I would like to confirm:

1. Are these the only compromised versions?
2. Which version is currently safe to use in production?
3. Is it safe to install the latest version now?

I am using Bun and planning to use Axios in a React project, so I want to make sure I am not installing any vulnerable or malicious version.

Thanks :)

```

### Drafted eval_question
```
I recently saw reports that some versions of Axios were compromised and contained malicious code. From what I understand, the affected versions were axios@1.14.1 and axios@0.30.4. I would like to confirm: 1. Are these the only compromised versions? 2. Which version is currently safe to use in production? 3. Is it safe to install the latest version now? I am using Bun and planning to use Axios in a React project, so I want to make sure I am not installing any vulnerable or malicious version.
```

**Flags:** Reporter cited: ['axios@1.14.1', 'axios@0.30.4']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/10642
**Title:** dont know if im infected
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Im new to the npm thing and i followed the stepguide to check if im infected dont know if im safe though

<img width="1105" height="281" alt="Image" src="https://github.com/user-attachments/assets/59e1fd11-6988-42d0-bd84-927cdd48a46b" />
<img width="644" height="110" alt="Image" src="https://github.com/user-attachments/assets/7fc5dcfe-7583-431e-a38f-f824112b08f5" />

<img width="1628" height="163" alt="Image" src="https://github.com/user-attachments/assets/fbfb0609-5b23-4a0f-8131-a2d491564126" />
```

### Drafted eval_question
```
I am new to using npm and followed a step-by-step guide to check if my system is infected. However, I am unsure if my system is safe. Can you help me determine if there is any security issue with my current setup?
```

**Flags:** NEEDS REVIEW

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/10636
**Title:** Post Mortem: axios npm supply chain compromise
**Repo:** axios/axios | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
Thanks for the writeup. Most of the stuff you mention here is already public knowledge. Would be great if you could add things that aren't publicly known yet. In particular, could you go into more detail on how they attacked you? This is still quite vague:

> About 2 weeks before March 31: social engineering campaign initiated against the lead maintainer

How did they trick you? What were the red flags in retrospect?

> This gave them access to the npm account credentials, which they used to publish the malicious versions.

How did they take over npm credentials? Didn't you have mandatory 2FA? Npm claims that all big packages have mandatory 2FA enabled. How did they circumvent that?
```

### Drafted eval_question
```
On March 31, 2026, two malicious versions of the axios library (1.14.1 and 0.30.4) were published to the npm registry due to a compromised maintainer account. These versions included a dependency, `plain-crypto-js@4.2.1`, which installed a remote access trojan on macOS, Windows, and Linux systems. The malicious versions were available for about 3 hours before removal. How did the attackers manage to bypass npm's mandatory 2FA for big packages, and what specific social engineering tactics were used to compromise the maintainer's account? Additionally, what are the recommended steps for users to determine if they were affected and to remediate the issue if they were?
```

**Flags:** Reporter cited: ['1.14.1', '0.30.4', 'plain-crypto-js@4.2.1']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/10614
**Title:** README beforeRedirect example bypasses follow-redirects credential-stripping protection
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
## Summary

The `beforeRedirect` config example in the README re-injects credentials **after** `follow-redirects` has stripped them for security, bypassing the library's built-in protection against credential leakage on protocol downgrades.

## The README example (Request Config section)

```js
beforeRedirect: (options, { headers }) => {
  if (options.hostname === "example.com") {
    options.auth = "user:password";
  }
},
```

## Why this is a problem

`follow-redirects` includes a security mechanism that [strips authorization headers when redirecting to a less secure protocol](https://github.com/follow-redirects/follow-redirects/blob/main/index.js#L469-L476) (HTTPS → HTTP) or to a different domain:

```js
// follow-redirects/index.js
if (redirectUrl.protocol !== currentUrlParts.protocol &&
   redirectUrl.protocol !== "https:" ||
   redirectUrl.host !== currentHost &&
   !isSubdomain(redirectUrl.host, currentHost)) {
  removeMatchingHeaders(/^(?:(?:proxy-)?authorization|cookie)$/i, th...
```

### Drafted eval_question
```
Is the `beforeRedirect` example in the axios README a security vulnerability because it re-injects credentials after `follow-redirects` has stripped them for security reasons? Specifically, does this example bypass the library's protection against credential leakage on protocol downgrades, such as from HTTPS to HTTP? Here is the problematic example from the README:

```js
beforeRedirect: (options, { headers }) => {
  if (options.hostname === "example.com") {
    options.auth = "user:password";
  }
},
```

The `follow-redirects` library includes a mechanism to strip authorization headers when redirecting to a less secure protocol or a different domain:

```js
// follow-redirects/index.js
if (redirectUrl.protocol !== currentUrlParts.protocol &&
   redirectUrl.protocol !== "https:" ||
   redirectUrl.host !== currentHost &&
   !isSubdomain(redirectUrl.host, currentHost)) {
  removeMatchingHeaders(/^(?:(?:proxy-)?authorization|cookie)$/i, this._options.headers);
}
```

The `beforeRedirect` callback fires after this stripping, potentially leading to credentials being sent over cleartext HTTP. Should the example include a protocol verification to prevent this security issue?
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/7417
**Title:** [v0.30.2/0.30.3] : Prototype pollution / DoS in mergeConfig (CVE-2026-25639)
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Hello Axios Team,

First, thank you for addressing the recent security vulnerability in v1.13.5.

We noticed that the same vulnerability affecting earlier versions (including the 0.x branch) was reportedly addressed in v0.30.3. However, security scanners (e.g., Snyk) are still flagging v0.30.3 as vulnerable.

Could you please clarify:

If there are additional patches planned for the 0.x branch?

Many enterprise projects are still dependent on the 0.x line, and confirmation of the security status (or an additional patch release if needed) would be greatly appreciated.

Thank you for your continued support and maintenance of Axios.

Best regards,
Vikram.
https://security.snyk.io/package/npm/axios/0.30.3

<img width="631" height="330" alt="Image" src="https://github.com/user-attachments/assets/a615e0c7-33b1-422a-a03b-889e293997cd" />

```

### Drafted eval_question
```
We noticed that the security vulnerability affecting earlier versions of Axios, including the 0.x branch, was reportedly addressed in v0.30.3. However, security scanners like Snyk are still flagging v0.30.3 as vulnerable. Could you please clarify if there are additional patches planned for the 0.x branch? Many enterprise projects are still dependent on the 0.x line, and confirmation of the security status or an additional patch release if needed would be greatly appreciated.
```

**Flags:** LEAK FLAGS: ['fixed_versions:v0.30.3'] | NEEDS REVIEW | Reporter cited: ['v0.30.3', 'v1.13.5', 'CVE-2026-25639']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/discussion/7302
**Title:** I have set withXSRFToken to true, but still do not see the header x-xsrf-token in the request - why?
**Repo:** axios/axios | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
Ah, @suryaprakash0010 I misunderstood. Reckon generating those token/header from backend is missing. This isn't mentioned in the documentation.

I'm using Express.js - which are the recommended npm libraries to use to generate them on backend?
```

### Drafted eval_question
```
I'm using the latest Axios version `1.13.2` with the following configuration:

```ts
const api = axios.create({
  baseURL: getAPIUrl(),
  // Enable credentials to allow cookies
  withCredentials: true,
  withXSRFToken: true,
});
```

When making a POST request, I do not see the `x-xsrf-token` header in the request. Why is this happening? Additionally, I'm using Express.js and need to know which npm libraries are recommended for generating XSRF tokens and headers on the backend.
```

**Flags:** Reporter cited: ['1.13.2']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/7228
**Title:** DeprecationWarning: url.parse() used in proxy resolution → Node DEP0169
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
DeprecationWarning: `url.parse()` used during Axios proxy resolution in Node (DEP0169)

When using Axios v1.13.2 in a Node/SSR environment, Axios triggers Node’s deprecation warning for `url.parse()`:

```
(node:XXXX) [DEP0169] DeprecationWarning: `url.parse()` behavior is not standardized and prone to errors that have security implications. Use the WHATWG URL API instead.
```

The stack trace consistently points to Axios’ internal proxy resolution path:

```
at urlParse (node:url:136:13)
at Object.getProxyForUrl (node_modules/proxy-from-env/index.js:…)
at setProxy (node_modules/axios/lib/…)
at dispatchHttpRequest (...)
```

This happens whenever Axios runs in Node with proxy support enabled (via HTTP_PROXY / HTTPS_PROXY / NO_PROXY env vars or Axios proxy configuration). The `proxy-from-env` package used internally still depends on `url.parse()`, which Node has deprecated under DEP0169.

Reproduction:

* Node.js v18+ or v20+
* Axios v1.13.2
* Any SSR environment (Next.js, Express, serv...
```

### Drafted eval_question
```
When using Axios v1.13.2 in a Node.js environment (v18+ or v20+), I encounter a deprecation warning related to `url.parse()` during proxy resolution, which is triggered by the `proxy-from-env` package. This warning is due to Node's DEP0169, which advises using the WHATWG URL API instead. The warning occurs when proxy support is enabled via environment variables or Axios configuration. This results in log pollution and potential security concerns as `url.parse()` is deprecated. Is there a plan to migrate Axios to use the WHATWG URL API for proxy resolution, or is there a way to disable proxy resolution to avoid this warning? Additionally, is there a fix or workaround available to address this issue?
```

**Flags:** Reporter cited: ['DEP0169', 'v1.13.2', 'v18+', 'v20+']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/7055
**Title:** Consider adopting npm trusted publishing
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Recent [supply chain attacks on npm](https://github.blog/security/supply-chain-security/our-plan-for-a-more-secure-npm-supply-chain/) have highlighted the need for stronger package publishing security. The September 2025 Shai-Hulud worm compromised 500+ packages through stolen maintainer tokens, showing the risks of token-based publishing.

Trusted publishing helps by eliminating long-lived tokens that can be stolen or accidentally exposed; generating automatic provenance provides cryptographic proof of where/how packages are built; and is an industry standard adopted by PyPI, RubyGems, crates.io, NuGet, etc.

Here's the short version:

1. [Configure a trusted publisher on npmjs.com](https://docs.npmjs.com/trusted-publishers#github-actions-configuration)
1. Add `id-token: write` permission to your workflow
1. Remove `NODE_AUTH_TOKEN` from your workflow

npm is [planning to deprecate legacy tokens](https://github.blog/security/supply-chain-security/our-plan-for-a-more-secure-npm-supply-...
```

### Drafted eval_question
```
Would the axios/axios project consider adopting npm trusted publishing to enhance package publishing security, in light of recent supply chain attacks on npm? This involves configuring a trusted publisher on npmjs.com, adding `id-token: write` permission to the workflow, and removing `NODE_AUTH_TOKEN` from the workflow. Additionally, it is necessary to ensure that the package requires 2FA to publish if not using OIDC, as the current CI workflow suggests that this setting might be off.
```

**Flags:** Reporter cited: ['e2bed7f84d86e87d0641bc5910e96607092d9934']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/7023
**Title:** Does CVE-2025-58754(Axios DoS via data: URL) affect the 0.x.x versions?
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
I saw that CVE-2025-58754(Axios DoS via data: URL decode) was mitigated [here](https://github.com/axios/axios/security/advisories/GHSA-4hjh-wcwx-xvwj).

I also saw that a new release was issued for `1.x.x` that contained this fix: https://github.com/axios/axios/releases/tag/v1.12.1

My question is - does this vulnerability affect `0.x.x` versions and if so when will a new release be created for it?
```

### Drafted eval_question
```
I saw that CVE-2025-58754 (Axios DoS via data: URL decode) was mitigated in a recent advisory and a new release was issued for version 1.x.x that contained this fix. Does this vulnerability affect the 0.x.x versions of Axios, and if so, when will a new release be created for it?
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2025-58754'] | NEEDS REVIEW | Reporter cited: ['CVE-2025-58754', 'GHSA-4hjh-wcwx-xvwj', 'v1.12.1']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/6975
**Title:** form-data uses unsafe random function in form-data for choosing boundary
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Can a maintainer please update axios to use form-data 4.0.4?

form-data uses unsafe random function in form-data for choosing boundary
https://github.com/advisories/GHSA-fjxv-7rqg-78g4

<img width="325" height="131" alt="Image" src="https://github.com/user-attachments/assets/ab062214-2e7c-4957-b7f5-05b818aafd62" />
```

### Drafted eval_question
```
Can a maintainer please update axios to use form-data 4.0.4? The current version of form-data uses an unsafe random function for choosing boundary, as detailed in the advisory: https://github.com/advisories/GHSA-fjxv-7rqg-78g4.
```

**Flags:** LEAK FLAGS: ['ghsa_ids:GHSA-fjxv-7rqg-78g4', 'fixed_versions:4.0.4', 'advisory_urls:https://github.com/advisories/GHSA-fjxv-7rqg-78g4'] | NEEDS REVIEW | Reporter cited: ['GHSA-fjxv-7rqg-78g4', '4.0.4']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/6969
**Title:** 🐛 Bug Report: Critical Vulnerability in Transitive Dependency form-data@4.0.0 via axios@1.10.0
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Describe the bug

Axios v1.10.0 introduces a critical vulnerability via its transitive dependency on form-data@4.0.0. According to [Snyk Security Advisory SNYK-JS-FORMDATA-10841150](https://security.snyk.io/vuln/SNYK-JS-FORMDATA-10841150), this version of form-data is affected by a Predictable Value Range from Previous Values issue, which can lead to HTTP parameter pollution and potentially allow boundary manipulation in multipart requests.

### To Reproduce

Install axios@1.10.0 and run a Snyk test:

```
npm install axios@1.10.0
npx snyk test

```
You’ll receive:

```
✗ Predictable Value Range from Previous Values [Critical Severity]
  in form-data@4.0.0 via axios@1.10.0 > form-data@4.0.0
  This issue was fixed in: 2.5.4, 3.0.4, 4.0.4
```



### Code snippet

```js

```

### Expected behavior

**Expected behavior**
Axios should avoid depending on a vulnerable version of form-data. The expected behavior is that form-`data@4.0.4` or higher is used to prevent exposure to known critic...
```

### Drafted eval_question
```
Axios v1.10.0 introduces a critical vulnerability via its transitive dependency on form-data@4.0.0. According to Snyk Security Advisory SNYK-JS-FORMDATA-10841150, this version of form-data is affected by a Predictable Value Range from Previous Values issue, which can lead to HTTP parameter pollution and potentially allow boundary manipulation in multipart requests. Is this behavior a genuine security vulnerability in axios@1.10.0 due to its dependency on form-data@4.0.0? Should Axios update its dependency to form-data@4.0.4 or higher to prevent exposure to this vulnerability?
```

**Flags:** Reporter cited: ['SNYK-JS-FORMDATA-10841150', '1.10.0', '4.0.0', '4.0.4']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/6931
**Title:** remove prepare script using husky and deprecated husky set from npm package
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Describe the bug

Hi Axios contributors,

While installing axios@1.9.0 as a transitive dependency in a monorepo, I’m encountering this error:
```
npm error .git can't be found
npm error > axios@1.9.0 prepare:hooks
npm error > npx husky set .husky/commit-msg "npx commitlint --edit $1"
npm error husky - install command is DEPRECATED

```
This appears to be caused by a prepare script in package.json that looks like this:
`"scripts": {
  "prepare": "husky install && npm run prepare:hooks",
  "prepare:hooks": "npx husky set .husky/commit-msg \"npx commitlint --edit $1\""
}`

This usage of husky in a published npm package breaks installation for consumers:
	•	It assumes a .git directory exists (which is not always true in monorepos or CI)
	•	It uses deprecated Husky commands (install, set)
	•	It runs developer-only tooling during install


Please consider removing the prepare script from the published package and move hook setup to a local-only husky:init script for contributors, e.g.:

...
```

### Drafted eval_question
```
Is the usage of a prepare script with Husky in axios@1.9.0 causing installation issues for consumers, particularly in monorepos or CI environments, due to assumptions about the presence of a .git directory and the use of deprecated Husky commands? Should the prepare script be removed from the published package and replaced with a local-only husky:init script for contributors?
```

**Flags:** Reporter cited: ['axios@1.9.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/6929
**Title:** Error 401 with the 'follow-redirects' library since version 1.15.8
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Describe the bug

Hello 

My project uses Axios 1.9.0,  and axios includes the following dependency:

`"dependencies": { "follow-redirects": "^1.15.6" }`

However, when the version of follow-redirects is >= 1.15.8, every POST request that returns a 303 with a Location URI fails with a 401 Unauthorized error.

To fix this, I added an override in my package.json:

`"overrides": { "axios": { "follow-redirects": "1.15.7" } }`

With this override, POST requests with redirects work correctly.

It looks like there’s a bug introduced in follow-redirects version 1.15.8.

The post in github follow redirects:

https://github.com/follow-redirects/follow-redirects/issues/277

### To Reproduce

_No response_

### Code snippet

```js

```

### Expected behavior

_No response_

### Axios Version

1.9.0

### Adapter Version

_No response_

### Browser

_No response_

### Browser Version

_No response_

### Node.js Version

20.18.1

### OS

_No response_

### Additional Library Versions

```bash

``...
```

### Drafted eval_question
```
I am experiencing an issue with Axios 1.9.0, which depends on 'follow-redirects'. When using 'follow-redirects' version 1.15.8 or higher, every POST request that returns a 303 with a Location URI fails with a 401 Unauthorized error. I have temporarily resolved this by overriding the dependency to use 'follow-redirects' version 1.15.7 in my package.json. Is this a known issue with 'follow-redirects' version 1.15.8, and is there a fix available for this problem?
```

**Flags:** Reporter cited: ['1.15.8', '1.15.7']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/discussion/6924
**Title:** Why is axios doing automatic redirects?
**Repo:** axios/axios | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
One interesting discovery: Axios comes with 3 adapters. `maxRedirects` is only implemented for the http adapter, but not for the xhr one. Sources:
- https://github.com/axios/axios/blob/v1.9.0/lib/adapters/http.js#L440
- https://github.com/axios/axios/blob/v1.9.0/lib/adapters/xhr.js

Why is XHR ignoring maxRedirects?

PS: this old discussion confirms it https://github.com/axios/axios/issues/3924#issuecomment-917666707
```

### Drafted eval_question
```
In my Single Page Application (SPA), unauthenticated users are not being redirected to the login page as expected when an API call returns a 302 status. I am using axios, and despite setting `maxRedirects` to zero, axios still follows redirects, making two requests. My code is as follows:

```ts
import axios, { isAxiosError } from "axios";

import { getAPIUrl } from "./options";
import { redirectDocument } from "react-router";

const api = axios.create({
  baseURL: getAPIUrl(),
  withCredentials: true,
  // Also disable automatic redirects since it's a SPA. We must listen to backend when to
  // redirect to the login page when unauthenticated.
  maxRedirects: 0,
});

api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (isAxiosError(error)) {
      if (error.response?.data?.location) {
        redirectDocument(error.response.data.location);
      } else {
        throw error;
      }
    } else {
      return Promise.reject(new Error(`Unprocessed Axios error in interceptor found: ${error.toString()}`));
    }
  },
);

export default api;
```

I discovered that axios has three adapters, and `maxRedirects` is only implemented for the http adapter, not for the xhr one. Why is the XHR adapter ignoring `maxRedirects`, and how can I prevent axios from following redirects in a SPA context?
```

**Flags:** Reporter cited: ['v1.9.0', 'https://github.com/axios/axios/issues/3924#issuecomment-917666707']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/6859
**Title:** Release 0.30.0 should be marked as a patched version for GHSA-jr5f-v2jv-69x6
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Hi,

Since release 0.30.0 includes #6829, it should be marked as a patched version for [GHSA-jr5f-v2jv-69x6](https://github.com/axios/axios/security/advisories/GHSA-jr5f-v2jv-69x6).

This update would allow GitHub to reflect the fix for the associated vulnerability, [CVE-2025-27152](https://nvd.nist.gov/vuln/detail/CVE-2025-27152).

I’d appreciate it if this could be updated. Thanks!
```

### Drafted eval_question
```
Should release 0.30.0 of the axios library be marked as a patched version for the vulnerability identified by GHSA-jr5f-v2jv-69x6, given that it includes the changes from pull request #6829? This update would help GitHub reflect the fix for the associated vulnerability, CVE-2025-27152.
```

**Flags:** LEAK FLAGS: ['ghsa_ids:GHSA-jr5f-v2jv-69x6'] | NEEDS REVIEW | Reporter cited: ['GHSA-jr5f-v2jv-69x6', 'CVE-2025-27152', '#6829', '0.30.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/6821
**Title:** axios 1.8.2 has the high OSS vulnerability
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
HI team regards to the axios-1.8.2 latest build has the OSS high security vulnerability when we scanned through blackduck, need your inputs here. 
```

### Drafted eval_question
```
Is there a high security vulnerability in axios version 1.8.2 related to the `allowAbsoluteUrls` parameter? It appears that this parameter is not part of `AxiosRequestConfig` and is used internally in axios/lib/adapters/http.js. Attempts to set it to false, as suggested in issue 6816, result in test case errors such as 'TypeError: URL is not a constructor'. How can this vulnerability be resolved, and should `allowAbsoluteUrls` default to false for versions >= v1.8.0?
```

**Flags:** Reporter cited: ['6816', 'v1.8.0', '1.8.2']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/6816
**Title:** BUG: Regarding the Fix Issue of CVE-2025-27152
**Repo:** axios/axios | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
> this is a opt-in explicitly change else we would be force to cut a major breaking version which would probably have just fragmented the versions even more.
> 
> we plan on doing a v2 with some great enhancements this year and then most of these new safety measures should become op-out explicitly

Any info on how we opt-in on 1.8.2? I couldn't find any relevant info in docs.
```

### Drafted eval_question
```
I am using axios version 1.8.2, which is supposed to have a fix for the vulnerability CVE-2025-27152. However, when I tested it using the provided Proof of Concept (PoC), the issue still seems to persist. Here is the code I used for testing:

```javascript
const axios = require('axios')

// The expectation is to send a request to port 12313.
const internalAPIClient = axios.create({
  baseURL: "http://127.0.0.1:12313/api/v1/users/",
  headers: {
    "X-API-KEY": "1234567890",
  },
});

// The attacker passes in //127.0.0.1:12314/
const userId = "http://127.0.0.1:12314/";

internalAPIClient.get(userId);
```

My `package.json` specifies:

```json
{
  "dependencies": {
    "axios": "^1.8.2"
  }
}
```

Is there a specific configuration or setting I need to apply to ensure the vulnerability is mitigated in this version?
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2025-27152'] | NEEDS REVIEW | Reporter cited: ['CVE-2025-27152', '1.8.2']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/6806
**Title:** Axios ignoring allowAbsoluteUrls configuration parameter
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Describe the bug

Starting from Axios v1.8.0, the `allowAbsoluteUrls` attribute was introduced in the configuration to control the use of absolute URLs. (PR: https://github.com/axios/axios/pull/6795)

Currently, this parameter is being ignored in the `buildFullPath` call from the HTTP adapter.

https://github.com/axios/axios/blob/72acf759373ef4e211d5299818d19e50e08c02f8/lib/adapters/http.js#L231

This oversight means that it is still possible to make requests to absolute URLs even when the `allowAbsoluteUrls` configuration attribute is set to `false`.

### Proof of Concept:

Even though `getUri` returns a URL from `example.com`, the request is sent to `evil.com`

```javascript
> const axios = require('axios');
> axios.VERSION
'1.8.1'
> const client = axios.create({baseURL: 'http://example.com/', allowAbsoluteUrls: false});
> client.getUri({url: 'http://evil.com'});
'http://example.com/http://evil.com'
> client.get('http://evil.com');
```

### Solution:

Include the `allowAbsoluteUr...
```

### Drafted eval_question
```
In Axios version 1.8.0, the `allowAbsoluteUrls` configuration parameter was introduced to control the use of absolute URLs. However, it appears that this parameter is being ignored in the `buildFullPath` function call within the HTTP adapter, allowing requests to absolute URLs even when `allowAbsoluteUrls` is set to `false`. Here is a proof of concept demonstrating the issue:

```javascript
const axios = require('axios');
const client = axios.create({baseURL: 'http://example.com/', allowAbsoluteUrls: false});
client.get('http://evil.com');
```

The expected behavior is that the request should be made to `example.com`, but it is instead sent to `evil.com`. Is this behavior a genuine security vulnerability in Axios, and how can it be resolved?
```

**Flags:** Reporter cited: ['1.8.0', 'https://github.com/axios/axios/pull/6795', '72acf759373ef4e211d5299818d19e50e08c02f8']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/6797
**Title:** package.json not add crypto
**Repo:** axios/axios | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
how it's possible? because npm versions cannot be changed if im not wrong. it was work yesterday, today how its gives error? could someone explain it me please?
```

### Drafted eval_question
```
In version 1.8.0 of the axios package, importing 'crypto' using `import crypto from 'crypto';` no longer works, although it was functioning yesterday. How is it possible for this error to occur if npm versions cannot be changed? Could someone explain why this might be happening?
```

**Flags:** Reporter cited: ['1.8.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/6776
**Title:** Question on TLS and Encryption Deprecation
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Describe the issue

Just looking to understand if support for TLS 1.1 and any of the older encryption algorithms are going to be deprecated at any point. 

### Example Code

```js

```

### Expected behavior

_No response_

### Axios Version

_No response_

### Adapter Version

_No response_

### Browser

_No response_

### Browser Version

_No response_

### Node.js Version

_No response_

### OS

_No response_

### Additional Library Versions

```bash

```

### Additional context/Screenshots

```bash

```
```

### Drafted eval_question
```
Will support for TLS 1.1 and any older encryption algorithms be deprecated in the axios library?
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/6625
**Title:** AxiosHeaders doesn't handle multiple headers returned via fetch adapter
**Repo:** axios/axios | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
Just chiming in here to say that I'm getting a similar issue where `AxiosHeaders.from` fails to parse headers as returned by Node's fetch function which are of type `Headers` instead of just a plain object. Not sure there is another issue already addressing this. Did anyone here make inroads on getting this resolved? Any assistance would be super helpful :)

```javascript
    const res = new Response(null, {
      status: 123,
      headers: {
        'X-Response-Code': 'Blah',
        'X-Response-Message': 'Blah blah',
      },
    })

    console.log(AxiosHeaders.from(res.headers))
```

Which outputs the following

```
Object [AxiosHeaders] { '[object Object]': undefined }
```
```

### Drafted eval_question
```
When using the fetch adapter in Node.js with Axios version 1.7.7, headers returned by the fetch function are not handled correctly by Axios. Specifically, multiple 'set-cookie' headers are overwritten instead of being collected into an array. The expected behavior is that repeated headers should be collected into an array format, similar to how Node.js handles them. Is this a bug in Axios, and how should the fetch adapter handle multiple headers, especially 'set-cookie'? Here is a code snippet demonstrating the issue:

```js
import axiosLib from "axios";

const axios1 = axiosLib.create({adapter: 'http', maxRedirects: 0, validateStatus: () => true}); 
const resp1 = await axios1.get("http://httpbin.org/cookies/set?a=x&b=y");
console.log('with http adapter', resp1.headers['set-cookie']);

const axios2 = axiosLib.create({adapter: 'fetch', maxRedirects: 0, validateStatus: () => true}); 
const resp2 = await axios2.get("http://httpbin.org/cookies/set?a=x&b=y", {
    fetchOptions: {
        redirect: 'manual'
    }
});
console.log('with fetch adapter', resp2.headers['set-cookie']);
```

The output shows that with the fetch adapter, only the last 'set-cookie' header is retained, whereas with the http adapter, all 'set-cookie' headers are collected into an array.
```

**Flags:** Reporter cited: ['1.7.7']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/6597
**Title:** Axios not using new header value in interceptor retried request
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Describe the issue

I have a response interceptor in which I would like to set new Auth header value so it might be used in retried request. Unfortunately the retried request does not update the header. I saw a few solutions, but none really helped me with this issue. I am currently using axios 1.7.7.

### Example Code

```js
import { useEffect } from 'react';
import { useRefreshToken } from './useRefreshToken';
import { useAuth } from './useAuth';
import { axiosPrivate, PrivateHttpClientConfig } from '../api';
import axios, { AxiosHeaders, InternalAxiosRequestConfig } from 'axios';

export const useAxiosPrivate = () => {
  const refreshToken = useRefreshToken();
  const { auth } = useAuth();

  useEffect(() => {
    const setAuthorizationHeader = (config: InternalAxiosRequestConfig) => {
      if (auth?.accessToken) {
        console.log(auth.access);
        config.headers.setAuthorization(`Bearer ${auth.accessToken}`);
      }
      return config;
    };

    const handleRefresh...
```

### Drafted eval_question
```
In axios version 1.7.7, I am trying to set a new Auth header value in a response interceptor so that it can be used in a retried request. However, the retried request does not update the header as expected. Here is the code I am using:

```js
import { useEffect } from 'react';
import { useRefreshToken } from './useRefreshToken';
import { useAuth } from './useAuth';
import { axiosPrivate, PrivateHttpClientConfig } from '../api';
import axios, { AxiosHeaders, InternalAxiosRequestConfig } from 'axios';

export const useAxiosPrivate = () => {
  const refreshToken = useRefreshToken();
  const { auth } = useAuth();

  useEffect(() => {
    const setAuthorizationHeader = (config: InternalAxiosRequestConfig) => {
      if (auth?.accessToken) {
        console.log(auth.access);
        config.headers.setAuthorization(`Bearer ${auth.accessToken}`);
      }
      return config;
    };

    const handleRefreshOnExpiredToken = async (error: unknown) => {
    
        if (axios.isAxiosError(error)) {
          const config = error.config as PrivateHttpClientConfig;
          const httpStatus = error.response?.status;
          console.log(config.headers);

          if (httpStatus === 401 && config && !config._retried) {
            config._retried = true;

            const newToken = await refreshToken();
            console.log('newToken', newToken);
            config.headers = { ...config.headers };
            config.headers.Authorization = `Bearer ${newToken}`;
            console.log(config.headers);
            return axiosPrivate.request(config);
          }
        }
        return Promise.reject(error);
    };
    const requestInterceptor = axiosPrivate.interceptors.request.use(
      setAuthorizationHeader,
      (error) => Promise.reject(error)
    );
    const responseInterceptor = axiosPrivate.interceptors.response.use(
      (request) => request,
      handleRefreshOnExpiredToken
    );

    return () => {
      axiosPrivate.interceptors.request.eject(requestInterceptor);
      axiosPrivate.interceptors.response.eject(responseInterceptor);
    };
  }, [auth, refreshToken]);
  return axiosPrivate;
};
```

Why is the new Auth header value not being used in the retried request, and how can I fix this?
```

**Flags:** LEAK FLAGS: ['fixed_versions:1.7.7'] | NEEDS REVIEW | Reporter cited: ['1.7.7']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/6545
**Title:** Security Vulnerability: Server-Side Request Forgery (SSRF) in Axios - CVE-2024-39338
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Describe the bug

**Body:**

Hello Axios Team,

I am reporting a high-severity security vulnerability related to Server-Side Request Forgery (SSRF) in Axios, identified as CVE-2024-39338. This vulnerability affects Axios versions 1.3.2 through 1.7.3, where path-relative URLs are incorrectly processed as protocol-relative URLs, leading to potential SSRF attacks.

**Why Reporting Here:**

I attempted to report this issue through your designated Huntr platform, as outlined in the SECURITY.md file. However, it appears that Axios is no longer listed or active on Huntr, which led me to report the issue directly through GitHub.

**Vulnerability Details:**

	•	`CVE: CVE-2024-39338`
	•	Affected Versions: Axios `>= 1.3.2`, `<= 1.7.3`
	•	Description: The vulnerability allows for SSRF via unexpected behavior where path-relative URLs are treated as protocol-relative URLs, potentially leading to exposure to external and internal services.
	•	Impact: This vulnerability can be exp...
```

### Drafted eval_question
```
Is there a genuine security vulnerability related to Server-Side Request Forgery (SSRF) in Axios, identified as CVE-2024-39338, affecting versions 1.3.2 through 1.7.3? The issue involves path-relative URLs being incorrectly processed as protocol-relative URLs, potentially leading to SSRF attacks. This vulnerability could allow unauthorized requests, potentially accessing sensitive data or systems. Can you confirm this vulnerability and provide guidance on addressing it?
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2024-39338'] | NEEDS REVIEW | Reporter cited: ['CVE-2024-39338', '>= 1.3.2', '<= 1.7.3']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/discussion/6542
**Title:** Server-Side Request Forgery
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
axios 1.7.2 allows SSRF via unexpected behavior where requests for path relative URLs get processed as protocol relative URLs. Is there a patch going on?
```

### Drafted eval_question
```
Does axios version 1.7.2 have a vulnerability that allows Server-Side Request Forgery (SSRF) due to unexpected behavior where requests for path relative URLs are processed as protocol relative URLs? Is there a patch being developed for this issue?
```

**Flags:** Reporter cited: ['1.7.2']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/6497
**Title:** React Native app works fine on ios but Axios network request in android
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### React Native app works fine on ios but Axios network request in android not working #6497


Will work fine in ios but in android it's not gonna send any requests. In flipper's network section i cant see any requests going out or coming in.
I'm not on localhost so replacing it with 10.0.0.2 won't help. 
my backend url is like http://x.x.x.x:8000

java version 20.0.0.2 
gradle version 8.3 
also tried many other java and gradle versions.

Here's the react-native info output.
System:
  OS: macOS 14.4.1
  CPU: (8) arm64 Apple M2
  Memory: 97.06 MB / 8.00 GB
  Shell:
    version: "5.9"
    path: /bin/zsh
Binaries:
  Node:
    version: 20.10.0
    path: ~/.nvm/versions/node/v20.10.0/bin/node
  Yarn:
    version: 1.22.21
    path: ~/.nvm/versions/node/v20.10.0/bin/yarn
  npm:
    version: 10.2.3
    path: ~/.nvm/versions/node/v20.10.0/bin/npm
  Watchman:
    version: 2024.07.01.00
    path: /usr/local/bin/watchman
Managers:
  CocoaPods:
    version: 1.15.2...
```

### Drafted eval_question
```
(ERROR — see eval_questions.jsonl)
```

**Flags:** NEEDS REVIEW | ERROR: LLM returned non-JSON: {
  "eval_question": "I am experiencing an issue where my React Native app works fine on iOS, but Axios network requests are not working on Android. The requests do not appear in Flipper's network section, and I am not using localhost, so replacing it with 10.0.0.2 is not applicable. My backend URL 

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/6463
**Title:** Server-Side Request Forgery Vulnerability (CVE-2024-39338)
**Repo:** axios/axios | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
Is there any way that we can fix this issue, as it is showing no patch available.

![image](https://github.com/user-attachments/assets/80dd5024-9c26-4955-a421-74cf44d45a52)

```

### Drafted eval_question
```
Is the behavior of Axios prior to version 1.3.2, where protocol-relative URLs are processed as valid URLs instead of raising an error, a genuine security vulnerability? Specifically, does this behavior allow for a Server-Side Request Forgery (SSRF) attack by enabling attackers to craft malicious protocol-relative URLs that are then requested by the server? Here is the example code demonstrating the issue:

```typescript
const axios = require('axios');

this.axios = axios.create({
  baseURL: 'https://userapi.example.com',
});

//userId = '12345';
userId = '/google.com'

this.axios.get(`/${userId}`).then(function (response) {
  console.log(`config.baseURL:  ${response.config.baseURL}`);
  console.log(`config.method:   ${response.config.method}`);
  console.log(`config.url:      ${response.config.url}`);
  console.log(`res.responseUrl: ${response.request.res.responseUrl}`);
});
```

Expected Output (Prior to axios 1.3.2):
```typescript
(node:10243) UnhandledPromiseRejectionWarning: TypeError [ERR_INVALID_URL]: Invalid URL: //example.org
```

Observed Output:
```yaml
config.baseURL:  https://userapi.example.com
config.method:   get
config.url:      //google.com
res.responseUrl: http://www.google.com/
```

Does this behavior introduce a security risk, and should Axios raise an error when attempting to request protocol-relative URLs server-side?
```

**Flags:** Reporter cited: ['CVE-2024-39338', '1.3.2']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/6459
**Title:** Pending requests with azure WAF
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Describe the issue

I'm encountering an issue where I make a POST request using axios, but it gets blocked by Azure WAF, resulting in a 403 status code. Following this, any subsequent requests I attempt to make with axios do not proceed and are indefinitely stuck in a pending state.
It appears as though the connection is perpetually frozen on the request that Azure rejected.
What could be causing this, and how can I avoid this situation?


```

### Drafted eval_question
```
I'm encountering an issue where I make a POST request using axios, but it gets blocked by Azure WAF, resulting in a 403 status code. Following this, any subsequent requests I attempt to make with axios do not proceed and are indefinitely stuck in a pending state. It appears as though the connection is perpetually frozen on the request that Azure rejected. What could be causing this, and how can I avoid this situation?
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## axios/axios/issue/6452
**Title:** v1.7.0 Unexpected token *
**Repo:** axios/axios | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Describe the bug

Uncaught SyntaxError: Unexpected token *
    at Object../node_modules/axios/lib/helpers/trackStream.js (login.js:1638)
    at __webpack_require__ (login.js:790)
    ……

chrome 62.0.3202.62 not support <async function*>

export const readBytes = async function* (iterable, chunkSize) {
  for await (const chunk of iterable) {
    yield* streamChunk(ArrayBuffer.isView(chunk) ? chunk : (await encoder.encode(String(chunk))), chunkSize);
  }
}

### To Reproduce

_No response_

### Code snippet

_No response_

### Expected behavior

_No response_

### Axios Version

_No response_

### Adapter Version

_No response_

### Browser

_No response_

### Browser Version

_No response_

### Node.js Version

_No response_

### OS

_No response_

### Additional Library Versions

_No response_

### Additional context/Screenshots

_No response_
```

### Drafted eval_question
```
In axios version 1.7.0, I encountered an 'Unexpected token *' error in Chrome version 62.0.3202.62, which does not support 'async function*'. The error occurs in the file 'trackStream.js'. Here is the relevant code snippet: 

export const readBytes = async function* (iterable, chunkSize) {
  for await (const chunk of iterable) {
    yield* streamChunk(ArrayBuffer.isView(chunk) ? chunk : (await encoder.encode(String(chunk))), chunkSize);
  }
}

Is this behavior expected, and how can I resolve this issue?
```

**Flags:** Reporter cited: ['v1.7.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/7196
**Title:** CI: consider adding npm dependency caching to setup-node step
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
I was exploring the CI workflow as part of my university project on GitHub Actions and noticed that the setup-node step doesn't currently include dependency caching.

The current setup-node step looks like this:

- uses: actions/setup-node@6044e13b5dc448c55e2357c09f80417699197238 # v6.2.0
  with:
    node-version: 'lts/*'

Adding cache: 'npm' would allow GitHub Actions to cache node_modules between runs, which can reduce install time on repeated builds:

- uses: actions/setup-node@6044e13b5dc448c55e2357c09f80417699197238 # v6.2.0
  with:
    node-version: 'lts/*'
    cache: 'npm'

I tested this on my own Node.js project and it worked without any other changes needed. I appreciate this may already be a considered decision, so happy to hear if there's a reason it's been left out.
```

### Drafted eval_question
```
I noticed that the CI workflow for the expressjs/express repository does not include dependency caching in the setup-node step. The current setup-node step is using actions/setup-node@6044e13b5dc448c55e2357c09f80417699197238 with node-version set to 'lts/*'. By adding cache: 'npm', GitHub Actions can cache node_modules between runs, potentially reducing install time on repeated builds. I tested this on my own Node.js project and it worked without any other changes. Is there a specific reason why npm dependency caching has not been included in the setup-node step?
```

**Flags:** Reporter cited: ['6044e13b5dc448c55e2357c09f80417699197238', 'v6.2.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/7143
**Title:** Vulnerable dependency version that is 12 years old: path-to-regexp
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
<!-- The process for bug fixing is:

- We will first assess if the behavior is different from what should occur
- Confirm the bug is reproducible
- Discuss how to best fix the bug
- Work towards a fix
-->

## Environment information

**Version**:
4.22.1
<!-- 
To find the installed version of a package, you can check the `package.json` file in the root directory of your project. The version will be listed under `dependencies` or `devDependencies`, like this:

```json
"dependencies": {
  "express": "4.18.2"
}
-->

**Platform**:
all platforms

**Node.js version**:
<!-- 
Output of node -v.
-->
22.x (irrelevant)

**Any other relevant information**:
https://security.snyk.io/package/npm/path-to-regexp
https://www.npmjs.com/package/path-to-regexp?activeTab=versions

## What steps will reproduce the bug?
running npm audit

```

### Drafted eval_question
```
I am using Express version 4.22.1 across all platforms, and I noticed that it depends on an outdated version of the 'path-to-regexp' package, which is 12 years old. Running 'npm audit' highlights this as a vulnerability. Is this a genuine security vulnerability in Express due to its dependency on 'path-to-regexp'? How should I address this issue?
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/7016
**Title:** Update body-parser dependency in https://github.com/expressjs/express/tree/4.x/ to `1.20.4`
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Currently at `1.20.3` containing malicious `qs` module version
```

### Drafted eval_question
```
Is the version 1.20.3 of the body-parser dependency in the expressjs/express repository affected by a malicious qs module, and should it be updated to version 1.20.4 to address this issue?
```

**Flags:** Reporter cited: ['1.20.3', '1.20.4']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/6978
**Title:** Vulnerability in express 5.2.1
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
On https://osv.dev//vulnerability/MAL-2025-192968 there is a reported security vulnerability in express 5.2.1 (reported on 30.12.2025). We got an according alert from Blackduck in our project, that analyzed our dependencies.

- How this vulnerability can be exploited? Just by installing 5.2.1 on a system?
- Are there other versions than 5.2.1 affected?
- Will there be a fix soon?
```

### Drafted eval_question
```
There is a reported security vulnerability in express 5.2.1 as noted on https://osv.dev//vulnerability/MAL-2025-192968. We received an alert from Blackduck regarding this issue in our project dependencies. How can this vulnerability be exploited? Is it exploitable just by installing version 5.2.1 on a system? Are there other versions besides 5.2.1 that are affected? Will a fix be released soon?
```

**Flags:** Reporter cited: ['MAL-2025-192968', '5.2.1']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/6968
**Title:** update to `qs@^6.14.1`
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
 
- Failure issue:
> - https://github.com/advisories/GHSA-6rw7-vpxm-498p 
- A few days ago, the following security flaw was discovered in lib qs. However, no issue or PR was found regarding this flaw or a possible solution.
- Projects that use Express are vulnerable and without solutions for the flaw.
- Please let us know when you can. Thank you!
```

### Drafted eval_question
```
A security flaw was discovered in the 'qs' library, as referenced in the advisory https://github.com/advisories/GHSA-6rw7-vpxm-498p. Projects using Express are vulnerable to this flaw. Can you update the 'qs' dependency in Express to ensure that the patched version is used by default?
```

**Flags:** LEAK FLAGS: ['ghsa_ids:GHSA-6rw7-vpxm-498p', 'advisory_urls:https://github.com/advisories/GHSA-6rw7-vpxm-498p'] | NEEDS REVIEW | Reporter cited: ['GHSA-6rw7-vpxm-498p']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/6874
**Title:** sendFile fails within .git folder
**Repo:** expressjs/express | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
Yet when I do this, I can access /.git/HEAD without issues?
```js
router.use("/.git", express.static(path.join(baseDir, ".git")));
```
```

### Drafted eval_question
```
In Express version 5.1.0 running on Windows 10 with Node.js v24.6.0, why does using `res.sendFile` to send a file from within a .git directory result in a NotFoundError, while `express.static` appears to work correctly with a .git root? Here is the code snippet used to reproduce the issue:

```js
const baseDir = path.join(import.meta.dirname, ".."); // Update as required by project structure
route.get("/test", (_, res) => {
    res.sendFile(path.join(baseDir, ".git/HEAD"));
});
```
Sending a request to /test triggers the error.
```

**Flags:** Reporter cited: ['5.1.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/6751
**Title:** Security audit with criticals
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Express 5.1.0 is giving this critical audit result since a couple of hours ago.

https://github.com/advisories/GHSA-8mgj-vmr8-frr6

Not sure what the right modus is here, run? hide?

Seems serious and I am having a difficult time getting it out of the dependencies, this debug package seems to be all over the place.

Any advise is welcome!

```

### Drafted eval_question
```
Express 5.1.0 is giving a critical audit result related to the advisory at https://github.com/advisories/GHSA-8mgj-vmr8-frr6. I am unsure how to proceed and am having difficulty removing the 'debug' package from the dependencies. Is this a serious issue, and what steps should I take to address it?
```

**Flags:** LEAK FLAGS: ['ghsa_ids:GHSA-8mgj-vmr8-frr6', 'advisory_urls:https://github.com/advisories/GHSA-8mgj-vmr8-frr6'] | NEEDS REVIEW | Reporter cited: ['GHSA-8mgj-vmr8-frr6', '5.1.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/6614
**Title:** location function does not validate potentially malicious URLs
**Repo:** expressjs/express | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
Hi,

I'm interested in working on this issue.

The current behavior of `res.location()` allowing `javascript:` or `data:` schemes in the `Location` header poses a significant **XSS vulnerability**, as browsers might execute such malicious URLs. While `encodeUrl` handles URL encoding, it doesn't validate the safety of the URL scheme itself.

I'd like to propose adding a **scheme validation** step within the `res.location` function. This would involve checking if the provided URL starts with safe schemes like `http://`, `https://`, or is a relative path (`/`). Any other schemes (e.g., `javascript:`, `data:`) would be rejected or handled safely to prevent this type of attack.

I believe this enhancement would significantly improve the **default security of Express** for all users.

Would it be possible for me to pick this up and submit a pull request? I'm happy to discuss the implementation details further.

Thanks,
Santiago
```

### Drafted eval_question
```
In Express version 5.0.0-beta.3, the `res.location()` function does not validate potentially malicious URLs, allowing schemes like `javascript:` to be set in the Location header, which can lead to XSS attacks. Should the `res.location()` function validate the URL scheme to reject or sanitize non-HTTP(S) URLs to prevent this security vulnerability?
```

**Flags:** Reporter cited: ['5.0.0-beta.3']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/6458
**Title:** 5.1.0 Throws error on route with a parameter in it
**Repo:** expressjs/express | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
Ah yeah, new path-to-regexp version breaking everything, let's break people's code for some made up by committee reason, good going guys.
```

### Drafted eval_question
```
I am encountering an error when using Express 5.1.0 with a route that includes a parameter. The error message is: 'TypeError: Missing parameter name at 1: https://git.new/pathToRegexpError'. My application code is as follows:

```js
import express from 'express';
import session from 'express-session';
import { sql } from 'slonik';
import { dbPool } from '../database/index.js';
const router = express.Router();

// API route for profile info
router.get('/api/users/:nickname', async (request, response) => {
  try {
    let nickname = request.params.nickname;
    // If no nickname is provided, check if the user is logged in
    if (!nickname && request.session.nickname) {
      nickname = request.session.nickname;
    }

    // If no nickname and no session, return an error
    if (!nickname) {
      response.status(401).json({ success: false, message: 'Not logged in or no nickname provided.' });
      return;
    }

    // Fetch the profile details for the given nickname
    const user = await dbPool.maybeOne(sql.unsafe`
			SELECT email, nickname, full_name, birthday FROM users WHERE nickname = ${nickname};
		`);

    // Check if the logged-in user is viewing their own profile
    const isOwner = request.session.nickname === nickname;

    // If the logged-in user is the owner, send full profile details
    if (isOwner) {
      response.status(200).json({
        success: true,
        profile: {
          email: user.email,
          nickname: user.nickname,
          fullName: user.full_name,
          dateOfBirth: user.birthday,
          isOwner: true,
        },
      });
      return;
    } else {
      // If it's a public view, send limited profile details
      response.status(200).json({
        success: true,
        data: {
          email: user.email,
          nickname: user.nickname,
          isOwner: false,
        },
      });
      return;
    }
  } catch (error) {
    console.error('Error fetching profile:', error);
    response.status(500).json({ success: false, message: 'Internal server error.' });
    return;
  }
});

export default router;
```

I initially used '/api/users/:nickname?' but changed it to '/api/users/{:nickname}' as per the migration guide, and then to '/api/users/:nickname' to make it a required parameter, but the error persists. My environment is Node.js v23.11.0 on Linux. Is this a bug in Express 5.1.0 or am I missing something in my implementation?
```

**Flags:** Reporter cited: ['5.1.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/6443
**Title:** res.redirect cannot carry the request header I set
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
![Image](https://github.com/user-attachments/assets/91c14e66-f7ce-4046-9b14-df73beda90f2)
```

### Drafted eval_question
```
I am using Express and encountering an issue where the `res.redirect` function does not carry the request header I set. I have confirmed that the ID is set in the header before forwarding. Is this expected behavior, or is there a way to ensure the header is preserved during a redirect?
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/6222
**Title:**  CVE-2024-10491 
**Repo:** expressjs/express | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
Can you confirm this is fixed as our NexusIQ scan is flagging this and we are currently on 4.21.2:

> ### Advisory Deviation Notice:
> The Sonatype Security Research team discovered that this vulnerability was introduced in version `3.0.0-beta4` and does not affect all versions through `3.1.24` as stated in the advisory. Additionally, the team discovered that this vulnerability affects all available `4.x` and `5.x` versions.
```

### Drafted eval_question
```
A vulnerability has been identified in the Express response.links function, allowing for arbitrary resource injection in the Link header when unsanitized data is used. This issue arises from improper sanitization in Link header values, which can allow a combination of characters like ,, ;, and <> to preload malicious resources. This vulnerability is especially relevant for dynamic parameters. Can you confirm if this vulnerability is fixed? Our NexusIQ scan is flagging this, and we are currently on version 4.21.2. The Sonatype Security Research team discovered that this vulnerability was introduced in version 3.0.0-beta4 and affects all available 4.x and 5.x versions.
```

**Flags:** Reporter cited: ['CVE-2024-10491', '3.0.0-beta4', '3.1.24', '4.21.2']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/6204
**Title:** Upgrade Version of debug package
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Hi, there!

IDK if it's the appropriate channel to discuss about that but the package [debug](https://www.npmjs.com/package/debug) in use of this app is on 2.6.9 version. And it has a problem of memory leak as discussed [here](https://github.com/debug-js/debug/issues/678).

This issue suggests upgrade this package to version 3.7.0 which this problem was already solved.

I  can also submit a Pull Request if it would help.
```

### Drafted eval_question
```
Is the memory leak issue in version 2.6.9 of the 'debug' package, as discussed in the linked issue, a concern for the expressjs/express repository? Should the package be upgraded to version 3.7.0 to resolve this problem?
```

**Flags:** Reporter cited: ['2.6.9', '3.7.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/6067
**Title:** CVE-2024-43800-serve-static
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
There is vulnerability in the latests scan for serve-static module.
└─┬ express@4.21.1 
  └── serve-static@1.16.2

```

### Drafted eval_question
```
Is there a security vulnerability in the serve-static module version 1.16.2 used by express version 4.21.1, as indicated by the latest scan?
```

**Flags:** Reporter cited: ['CVE-2024-43800']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/6053
**Title:** CVE-2024-47764 from cookie-0.6.0
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
I'm using express-4.21.0.

I've had a Mend report of a medium risk from cookie-0.6.0 for a week now (CVE-2024-47764). A week ago this was also reported via npm audit (as a low level risk). Now it's not even that as npm reports 0 vulnerabilities.

Has this issue been downgraded? It's still reported in Mend. Are there any plans on updating express 4 to use cookie-0.7.0 to fix the issue?

```

### Drafted eval_question
```
I'm using express-4.21.0 and received a Mend report indicating a medium risk from cookie-0.6.0 due to CVE-2024-47764. Initially, npm audit also reported this as a low-level risk, but now npm reports 0 vulnerabilities. Has this issue been downgraded? It's still reported in Mend. Are there any plans to update express 4 to use cookie-0.7.0 to address this issue?
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2024-47764'] | NEEDS REVIEW | Reporter cited: ['CVE-2024-47764', 'cookie-0.6.0', 'cookie-0.7.0', 'express-4.21.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/5970
**Title:** express using older version of path-to-regex, which is causing us the operational vulnerability in our project. 
**Repo:** expressjs/express | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
According to aquasec, this is still an issue in version 0.1.10 because of an incomplete fix (see info here: https://avd.aquasec.com/nvd/2024/cve-2024-52798/). Could you update path-to-tegex to 0.1.12 in the 4.x branch? I'm also having vulnerability reports in my project.
```

### Drafted eval_question
```
Is the use of path-to-regexp version 0.1.10 in express version 4.x a security vulnerability, and should it be updated to a newer version like 8.0.0 to address this issue? According to Snyk and Aquasec, version 0.1.10 is vulnerable, and I am receiving vulnerability reports in my project. Can express version 4.x be updated to use a non-vulnerable version of path-to-regexp?
```

**Flags:** Reporter cited: ['0.1.10', '8.0.0', '8.1.0', '4.18.2', '4.21.0', 'https://security.snyk.io/package/npm/path-to-regexp/0.1.10', 'https://www.npmjs.com/package/express/v/4.21.0?activeTab=code', 'https://avd.aquasec.com/nvd/2024/cve-2024-52798/']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/5968
**Title:** Dependency: Bump path-to-regexp in v4 to fix security vulnerability. 
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Bump dep path-to-regexp to fix https://github.com/advisories/GHSA-9wv6-86v2-598j

https://github.com/expressjs/express/blob/4.x/package.json#L50
```

### Drafted eval_question
```
Is there a security vulnerability in the 'path-to-regexp' dependency used in Express.js version 4, and does updating to version 0.1.10 of 'path-to-regexp' resolve this issue?
```

**Flags:** LEAK FLAGS: ['fixed_versions:0.1.10'] | NEEDS REVIEW | Reporter cited: ['GHSA-9wv6-86v2-598j']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/5948
**Title:** Express 5.0.0 Route with regex not working
**Repo:** expressjs/express | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
Is it realtes to https://blakeembrey.com/posts/2024-09-web-redos/ and https://github.com/advisories/GHSA-9wv6-86v2-598j?
But I don't understand, why the major version of "path-to-regexp" was updated when express@5 was released?
```

### Drafted eval_question
```
In an Express 5.0.0 application using Node.js v20.10.0, the following code snippet throws a TypeError related to the path-to-regexp module when attempting to define a route with a regex pattern:

```javascript
const express = require('express')
const app = express()
const port = 4000

function logErrors(err, req, res, next) {
    console.error(err.stack)
    next(err)
}

function clientErrorHandler(err, req, res, next) {
    if (req.xhr) {
        res.status(500).send({ error: 'Something failed!' })
    } else {
        next(err)
    }
}
function errorHandler (err, req, res, next) {
   
    res.status(err.statusCode || 500)
    res.json({ message: err.message || "something wrong" })
}

app.get('/', async (req, res) => {
    await Promise.reject({"message":"dsfjh", statusCode: 400})
    res.status(200).send("asfas")
})

app.get('/[discussion|page]/:slug', async (req, res) => {
    throw {statusCode: 400, message: "harish"}
    res.status(200).send("asfas")
})


app.use(logErrors)
app.use(clientErrorHandler)
app.use(errorHandler)

app.listen(port, () => {
    console.log(`Example app listening on port ${port}`)
})
```

The error message is:

```
~/express5/node_modules/path-to-regexp/dist/index.js:136
        throw new TypeError(`Unexpected ${nextType} at ${index}, expected ${type}: ${DEBUG_URL}`);
        ^

TypeError: Unexpected [ at 1, expected END: https://git.new/pathToRegexpError
    at Iter.consume (~/express5/node_modules/path-to-regexp/dist/index.js:136:15)
    at consume (~/express5/node_modules/path-to-regexp/dist/index.js:193:16)
    at parse (~/express5/node_modules/path-to-regexp/dist/index.js:197:20)
    at ~/express5/node_modules/path-to-regexp/dist/index.js:308:74
    at Array.map (<anonymous>)
    at pathToRegexp (~/express5/node_modules/path-to-regexp/dist/index.js:308:25)
    at Object.match (~/express5/node_modules/path-to-regexp/dist/index.js:278:30)
    at matcher (~/express5/node_modules/router/lib/layer.js:83:23)
    at new Layer (~/express5/node_modules/router/lib/layer.js:90:62)
    at Function.route (~/express5/node_modules/router/index.js:421:17)
```

Is this behavior a genuine issue with the path-to-regexp module, and how should I modify my route definitions to work with Express 5.0.0?
```

**Flags:** Reporter cited: ['Node.js v20.10.0', 'express 5.0.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/5947
**Title:** npm audit fail on last Express version (4.20.0) due to send(0.19.0) vulnerability
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Bug Report: npm audit fails on latest Express version (4.20.0) due to send(0.19.0) vulnerability

Issue Description

Running npm audit on the latest version of Express (4.20.0) fails due to a moderate severity vulnerability in send (<0.19.0).


Here’s the relevant output from npm audit:

# npm audit report send <0.19.0
Severity: moderate
send vulnerability to template injection can lead to XSS - http://github.com/advisories/GHSA-m6fv-jmcg-4jfg
No fix available

Steps to reproduce

npm install express --save



```

### Drafted eval_question
```
Is the npm audit failure on the latest Express version (4.20.0) due to the send package vulnerability a genuine security concern, and is there a fix available for this issue? The audit report indicates a moderate severity vulnerability in send (<0.19.0) related to template injection that can lead to XSS.
```

**Flags:** LEAK FLAGS: ['fixed_versions:0.19.0'] | NEEDS REVIEW | Reporter cited: ['GHSA-m6fv-jmcg-4jfg', '4.20.0', '0.19.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/5943
**Title:** Mismatched dependency versions
**Repo:** expressjs/express | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
There is another one that should be urgently looked at by the maintainers:

This is new version it is important to update: https://github.com/pillarjs/encodeurl/releases/tag/v2.0.0

Express is on latest, but [`serve-static`](https://github.com/expressjs/serve-static/tree/1.x) is still using the vulnerable version.

Edit: This also affects [`send`](https://github.com/pillarjs/send/tree/v0.x) and [`finalhandler`](https://github.com/pillarjs/finalhandler/tree/1.x)

The workaround for now is (and it may not be possible for everyone if other dependencies use a completely different version):
```
  "overrides": {
    "encodeurl": "~2.0.0",
    "qs": "^6.13.0",
    "send": "^0.19.0"
  },
```

My two cents.
```

### Drafted eval_question
```
Is there a security vulnerability in the Express and serve-static packages due to mismatched dependency versions? Specifically, Express requires "qs": "6.11.0" while body-parser uses "qs": "6.13.0", and serve-static requires "send": "0.18.0" while Express requires "send": "0.19.0". Additionally, serve-static is using a vulnerable version of encodeurl, which should be updated to version 2.0.0. Should these dependencies be updated to the following versions to address potential issues? 

```
"qs": "6.13.0",
"send": "0.19.0",
"encodeurl": "~2.0.0"
```

Related issues and PRs have been opened, but is there an urgent need for maintainers to address these mismatches?
```

**Flags:** LEAK FLAGS: ['fixed_versions:2.0.0'] | NEEDS REVIEW | Reporter cited: ['6.11.0', '1.20.3', '6.13.0', '1.16.0', '0.19.0', '0.18.0', '2.0.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/discussion/5852
**Title:** POST request causing PreFlight and then getting cancelled after stalling
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
I wrote  a simple API for learning using express, when I try to send a POST request from POSTMAN it is carried out and returns a success message but when POST is sent from client, PreFlight is issued and POST request after being stalled gets cancelled, after which PreFlight does return "204 No Content" success message. 
1. PreFlight must not be issued during POST request ?
2. if it does how to make sure it does that it does not stall the POST request, or how to increase the timeout for POST request?

my  client side code is: 
```
  button.onclick = addElement=> {
            var key = document.getElementById('key').value;
            console.log("button clicked");
            var value = document.getElementById('value').value;
        
            console.log(key);
            var options = {
                method : "POST",
                headers : {'Content-Type': 'application/json'},
                body : JSON.stringify({
                    'key':key,
           ...
```

### Drafted eval_question
```
I wrote a simple API using Express, and when I send a POST request from Postman, it succeeds. However, when the POST request is sent from the client, a PreFlight request is issued, and the POST request gets stalled and then cancelled. The PreFlight request returns a '204 No Content' success message. 

1. Should a PreFlight request be issued during a POST request?
2. If a PreFlight request is issued, how can I ensure it doesn't stall the POST request, or how can I increase the timeout for the POST request?

Here is my client-side code:

```javascript
button.onclick = addElement => {
    var key = document.getElementById('key').value;
    console.log('button clicked');
    var value = document.getElementById('value').value;

    console.log(key);
    var options = {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            'key': key,
            'value': value
        })
    };
    console.log('initializing POST');
    const fet = fetch('https://skiadrum.herokuapp.com/data', options).then(response => {
        console.log(response);
        return response.json();
    }).then(response => {
        console.log(response);
        document.getElementById('api_response').innerHTML = response;
    }).catch(error => {
        console.log('post request failed');
        console.error(error);
    });
}
```

And the server POST request handler is:

```javascript
var postCorsOptions = {
    'origin': ['http://127.0.0.1:5500', 'http://127.0.0.1:5501'],
    'methods': 'GET,HEAD,PUT,PATCH,POST,DELETE',
    'preflightContinue': false,
    'optionsSuccessStatus': 204,
    'Content-Type': 'appllication/json'
}

app.post('/data', cors(postCorsOptions), (request, response) => {
    var file = request.body;
    console.log(file.value);
    console.log('post request received in server');
    reply = {
        'status': 'success',
        'data_received': {
            'key': request.body.key,
            'value': request.body.value
        }
    }
    score[request.body.key] = request.body.value;
    try {
        fs.writeFile('score.json', JSON.stringify(score, null, 2), err => {
            console.log('writing into the file from post request');
        });
    } catch (error) {
        console.error(error);
    }

    response.send(reply);
});
```
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/5698
**Title:** Impossible to catch the cookie client side 
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Hi,i have a issue and now t 72 hour i am  block on that.

I have my website separate in 2 parties:

**back end with express

front end with next js**

I use the express part for the connection on the client side with discord.

On localhost no issue i have my cookie client side and on the back end side too so it works.

But on vercel on production impossible to have the cookie o the client but what is strange on the URL of redirection of passport discord the cookie is set but just the back end have it...

**Now lets go to the code part:**

app.js
```javascript
require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const path = require('path');
const cookieParser = require('cookie-parser');

//routes
const routes = require('./routes/index');

//init app
const app = express();
app.use(express.json());
app.use(cookieParser());
app.use(express.urlencoded({ extended: true }));

// D...
```

### Drafted eval_question
```
(ERROR — see eval_questions.jsonl)
```

**Flags:** NEEDS REVIEW | ERROR: LLM returned non-JSON: {
  "eval_question": "I am experiencing an issue with my website, which is divided into a backend using Express and a frontend using Next.js. On localhost, everything works fine, and I can access cookies on both the client and server sides. However, in production on Vercel, the cookie is set during 

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/5688
**Title:** Issue with parsing url query
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Hi there, 

I think I may have found a very weird issue with parsing arrays inside the query of a url sent to express. Now as far as I know, the parsing here is handled by another package (qs), however as the latest express version (v4.19.2) does not use the latest qs version (from what I could tell from my package.lock), I though it best to post this issue here first. 

Basically I have been using the following format to pass arrays through the query for GET calls:

....&filter[a][0]=randomId1&filter[a][1]=randomId2&....

And this worked perfectly for a pretty long time. I only found an issue when the array I was passing had a 21st index (filter[a][21]). Once this happened, the parsing still worked, but rather then having req.query.a (this case) of type 'array', it was instead on object, with numbered indexes. This, of course, broke some of my logic later on, so that's how I came to find out about.

I'm not sure if this is happening due to having an outdated version of 'qs',...
```

### Drafted eval_question
```
I am experiencing an issue with Express (v4.19.2) when parsing arrays in URL queries. The parsing is handled by the 'qs' package, and I suspect the issue might be due to Express not using the latest version of 'qs'. When I pass arrays in the query string using the format '&filter[a][0]=randomId1&filter[a][1]=randomId2&...', it works fine until the array has a 21st index (e.g., filter[a][21]). At that point, instead of 'req.query.a' being an array, it becomes an object with numbered indexes, which breaks my logic. Could this be due to an outdated 'qs' version, and should Express update 'qs' to resolve this? I have created a small reproduction in a public repository: https://github.com/MaurovicCachiaSE/snippets.git in the folder express-array-issue.
```

**Flags:** Reporter cited: ['v4.19.2']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/5651
**Title:** EDIT: False positive - HIGH vulnerability in dependency used, Cookie 0.6.0
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
We are importing a vulnerability here:
https://github.com/expressjs/express/blob/04bc62787be974874bc1467b23606c36bc9779ba/package.json#L36C1-L36C23

Can we please upgrade to version 0.7.6 or higher?

CVSS score 7.5 in this library
https://github.com/advisories/GHSA-vjrq-cg9x-rfjp
(fixed versions in ticket)
```

### Drafted eval_question
```
We are concerned about a high vulnerability in the 'cookie' library version 0.6.0, which is imported in the expressjs/express repository. The CVSS score for this vulnerability is 7.5. Can we please upgrade to version 0.7.6 or higher to address this issue? The vulnerability is detailed in this advisory: https://github.com/advisories/GHSA-vjrq-cg9x-rfjp.
```

**Flags:** LEAK FLAGS: ['ghsa_ids:GHSA-vjrq-cg9x-rfjp', 'advisory_urls:https://github.com/advisories/GHSA-vjrq-cg9x-rfjp'] | NEEDS REVIEW | Reporter cited: ['0.6.0', '0.7.6', 'GHSA-vjrq-cg9x-rfjp']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/5516
**Title:** How to run an app after installing certificates for localhost
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Hi everyone, I need some help because I'm very new doing all of this.
Currently, I have myapp running perfectly on http://localhost/myapp
Now, I would like to have it running on https://localhost/myapp
I have correctly installed the certificates and the https://localhost is on and it displays a message: "Hello, HTTPS World!"
Now, how can I run myapp on https://localhost/myapp ??

myapp is a directory located in C:\Apache24\htdocs\myapp

The code of my server.js file is:
`const app = require('express')();`
`const https = require('https');`
`const fs = require('fs');`

`const options = {`
`    key: fs.readFileSync('build/cert/server.key'),`
`    cert: fs.readFileSync('build/cert/server.crt'),`
`}`
`https.createServer(options, (req, res) => {`
`  res.writeHead(200);`
`  res.end('Hello, HTTPS World!');`
`}).listen(443, () => {`
`  console.log('Server is running on port 443');`
`});`

OS: Win 10
Any help or hint will be much appreciated.

```

### Drafted eval_question
```
How can I configure my Express application to run on https://localhost/myapp after installing certificates? My current setup runs on http://localhost/myapp, and I have successfully installed certificates to display a message on https://localhost. My application directory is located at C:\Apache24\htdocs\myapp, and my server.js file is as follows:

const app = require('express')();
const https = require('https');
const fs = require('fs');

const options = {
    key: fs.readFileSync('build/cert/server.key'),
    cert: fs.readFileSync('build/cert/server.crt'),
}
https.createServer(options, (req, res) => {
  res.writeHead(200);
  res.end('Hello, HTTPS World!');
}).listen(443, () => {
  console.log('Server is running on port 443');
});

I am using Windows 10.
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/5459
**Title:** Allow reading Forwarded header as alternative to X-Forwarded-
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
A few service providers / proxy servers are beginning to use [Forwarded](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Forwarded) header instead of [X-Forwarded-For](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Forwarded-For) and related headers. This includes AWS's HTTP API Gateway.

Express does not currently support this header, and I can see no way of hooking up the trust proxy mechanism manually to parse this header, so I am a bit stuffed.

Can you either provide a config setting to use this header for trust proxy, or suggest an alternative way to get this to work?
```

### Drafted eval_question
```
A few service providers and proxy servers, including AWS's HTTP API Gateway, are starting to use the Forwarded header instead of the X-Forwarded-For and related headers. Express does not currently support the Forwarded header, and I cannot find a way to manually configure the trust proxy mechanism to parse it. Can you provide a configuration setting to use the Forwarded header for trust proxy, or suggest an alternative method to achieve this?
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/5449
**Title:** feature: add a GitHub action to quell spam PRs
**Repo:** expressjs/express | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
> In most projects that I am involved the moderation is done by the humans behind the project or a specific team that volunteer to do it, it is a heavy job. The same way as it is hard to keep a slack/discord/gitter community channel a safe space by moderating content.

I think historically the express project has not needed the same style of moderation as things like Node.js does. There have been less contentious discussions and mostly the CoC violations have come from folks outside the project so it was relatively simple to ban and move on. I don't think we need to immediately spin up a moderation team but I do think that the Triage team and TC should have the tools to properly moderate. Right now I don't think we have that well in hand. I believe that we can add this to the list of TODOs to address after we can get next weeks TC meeting organized and finished.

Are we in agreement that a GH Action is most likely not the direction we would want to take to solve this problem?
```

### Drafted eval_question
```
Is there a way to implement a GitHub action or workflow to automatically detect and close spam pull requests in the expressjs/express repository? These spam PRs often involve minimal changes to the README.md file, have default commit messages like 'Update filename', and lack descriptions. Additionally, many of these PRs are submitted by users with a repository named 'localrepo'. Could a rule-based system or an AI-based detection method be effective in managing this issue?
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/5353
**Title:** Routing bug - URIError: Failed to decode param '$%^'
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Hi There,

I have found this weird bug in routing. Any API route param if contains these 3 characters in this sequence "**$%^**" it breaks the router and crashed. I need help how to prevent this from happening.

`URIError: Failed to decode param &#39;12321$%^4ABCD&#39;<br> &nbsp; &nbsp;at decodeURIComponent (&lt;anonymous&gt;)`

**Express Route:**
![express_route](https://github.com/expressjs/discussions/assets/62402545/cc4a2f06-5fd9-416a-b711-e30d77ba72c7)

**Valid Call**
![express_route_valid_call](https://github.com/expressjs/discussions/assets/62402545/4b3bd0fd-6f14-44d5-a02c-feccea72be18)

**Invalid Call**
![express_route_invalid_call](https://github.com/expressjs/discussions/assets/62402545/19484b30-8f29-4102-ab4d-2c2af4083be4)

```

### Drafted eval_question
```
I have encountered a bug in Express routing where any API route parameter containing the characters '$%^' in sequence causes the router to crash with the error: `URIError: Failed to decode param '12321$%^4ABCD' at decodeURIComponent`. How can I prevent this issue from occurring?
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/5344
**Title:** Can express req.headers[x] be an array?
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
@types/express indicates that various specified headers may be strings or undefined, but also that it may have other entries, which may be strings or arrays of strings.
```ts
 interface IncomingHttpHeaders extends NodeJS.Dict<string | string[]> {
    accept?: string | undefined;
    "accept-language"?: string | undefined;
    "accept-patch"?: string | undefined;
    ...
}
```
Is this typing correct? Are there any circumstances where express would add arrays to the headers list?

If so, what form would the content of these arrays be, and how could they be combined safely into a single string?

Thanks.
```

### Drafted eval_question
```
In Express, can the req.headers object contain arrays of strings for any headers, as suggested by the @types/express typings? If so, under what circumstances would Express add arrays to the headers list, and how should these arrays be safely combined into a single string?
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/5292
**Title:** Report
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Why is expressjs still using debug@2.6.9 ? Security scans show that this version is vulnerable to CWE-401 and CWE-1333.
Please update to latest version.
```

### Drafted eval_question
```
Why is expressjs still using debug@2.6.9? Security scans show that this version is vulnerable to CWE-401 and CWE-1333. Please update to the latest version.
```

**Flags:** Reporter cited: ['CWE-401', 'CWE-1333', '2.6.9']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## expressjs/express/issue/5275
**Title:** Unable to create Partitioned cookie
**Repo:** expressjs/express | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
The Partitioned attribute is not set when passing the option to res.cookie(). 

https://developer.chrome.com/docs/privacy-sandbox/third-party-cookie-phase-out/#partitioned-cookies
```

### Drafted eval_question
```
Is there a solution for setting the Partitioned attribute in cookies using Express 4.18.2? I am using the cookie-parser package, but when I attempt to set a cookie with the partitioned option using res.cookie(), it does not appear in the network tab. Here's the code I'm using:

```js
res.cookie('cookie-name', 'cookie-value', { partitioned: true });
```

I've also tried using the native res.setHeader() with the jshttp cookie package as a workaround:

```js
const cookie = require('cookie');

res.setHeader(
    'Set-Cookie',
    cookie.serialize('session_id', String(session_id), {
        path: '/',
        httpOnly: true,
        maxAge: 86400,
        secure: true,
        sameSite: 'none',
        partitioned: true,
    })
);
```

Is there an official update or a better workaround for this issue?
```

**Flags:** Reporter cited: ['4.18.2']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## fastapi/fastapi/issue/13471
**Title:** Basic auth `realm` is REQUIRED but handled as optional
**Repo:** fastapi/fastapi | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
According to https://datatracker.ietf.org/doc/html/rfc7617#autoid-3 , specification of the `realm` parameter is REQUIRED, so making `realm` optional here

https://github.com/fastapi/fastapi/blob/643d2845de09a437b955a163ab25eb0887bfd0e1/fastapi/security/http.py#L195

and at related places, is misleading and makes it easy to create non-conforming APIs. It bit me when a Shelly device refused (rightfully) to authenticate against the API which was using the default (missing) `realm` behavior.

```

### Drafted eval_question
```
In FastAPI, the `realm` parameter for basic authentication is currently optional, but according to RFC 7617, it is required. This optional handling can lead to non-conforming APIs, as I experienced when a Shelly device refused to authenticate due to the missing `realm`. Is making `realm` optional in FastAPI a security vulnerability or a compliance issue? Additionally, is setting a default `realm` value to 'global' appropriate, given that this string is often presented to users as a prompt for credentials?
```

**Flags:** Reporter cited: ['643d2845de09a437b955a163ab25eb0887bfd0e1']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## fastapi/fastapi/issue/11104
**Title:** [BUG] Upgrade python-mulipart==0.0.7 from low version fastapi upload file may be 400
**Repo:** fastapi/fastapi | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Privileged issue

- [X] I'm @tiangolo or he asked me directly to create an issue here.

### Issue Content

> In order to fix the [security issue](https://github.com/tiangolo/fastapi/security/advisories/GHSA-qf9m-vfgh-m389) of uploaded files, we upgraded the python-mulipart library, but this caused "There was an error parsing the body" to appear frequently when uploading files.
![image](https://github.com/tiangolo/fastapi/assets/53138073/ab35a6fd-ca76-4009-b225-bf821c362165)

- macos: 14.2.1 
- fastapi: 0.94.1
- python-multipart: 0.0.7 
```

### Drafted eval_question
```
After upgrading the python-multipart library to version 0.0.7 to address the security issue in FastAPI related to uploaded files, we are encountering frequent errors with the message 'There was an error parsing the body' when uploading files. We are using FastAPI version 0.94.1 on macOS 14.2.1. Due to significant changes in FastAPI versions after 0.94.1, we cannot upgrade FastAPI at this time. How can we resolve the file upload errors while maintaining security?
```

**Flags:** Reporter cited: ['GHSA-qf9m-vfgh-m389', '0.94.1', '0.0.7']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## fastapi/fastapi/issue/10177
**Title:** HTTPBearer security scheme is returning 403 instead or 401
**Repo:** fastapi/fastapi | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Discussed in https://github.com/tiangolo/fastapi/discussions/9130

<div type='discussions-op-text'>

<sup>Originally posted by **aaaaahaaaaa** September  8, 2020</sup>
HTTPBearer security scheme enabled as a dependency is returning a `403` when a request is unauthenticated because of a missing or a malformed `authorization` header. In those scenarios, a `401` should be returned instead.</div>

## Related PRs
- https://github.com/tiangolo/fastapi/pull/2120
- https://github.com/tiangolo/fastapi/pull/5310
- https://github.com/tiangolo/fastapi/pull/5332
- https://github.com/tiangolo/fastapi/pull/9312
```

### Drafted eval_question
```
In FastAPI, when using the HTTPBearer security scheme as a dependency, an unauthenticated request due to a missing or malformed 'authorization' header is returning a 403 status code. Shouldn't it return a 401 status code instead? This issue seems to affect not only HTTPBearer but also other classes in the security scope, such as OAuth2 and HTTPBase, which return 403 in 'Not authenticated' cases where a 401 might be more appropriate. Is this behavior intentional, and will there be any changes to address this discrepancy?
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## fastapi/fastapi/issue/5837
**Title:** The browser cannot receive cookies from FastAPI set_cookie methods
**Repo:** fastapi/fastapi | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### First Check

- [X] I added a very descriptive title to this issue.
- [X] I used the GitHub search to find a similar issue and didn't find it.
- [X] I searched the FastAPI documentation, with the integrated search.
- [X] I already searched in Google "How to X in FastAPI" and didn't find any information.
- [X] I already read and followed all the tutorial in the docs and didn't find an answer.
- [X] I already checked if it is not related to FastAPI but to [Pydantic](https://github.com/samuelcolvin/pydantic).
- [X] I already checked if it is not related to FastAPI but to [Swagger UI](https://github.com/swagger-api/swagger-ui).
- [X] I already checked if it is not related to FastAPI but to [ReDoc](https://github.com/Redocly/redoc).

### Commit to Help

- [X] I commit to help with one of those options 👆

### Example Code

```python
@app.post('/login', summary='Create access and refresh tokens for user', response_model=TokenSchema)
async def login(form_data: OAuth2PasswordRequestForm = D...
```

### Drafted eval_question
```
I am using FastAPI version 0.88.0 on macOS with Python 3.10.5 for the backend (running on port 8000) and Solid-JS for the frontend (running on port 3000). I want to send a refresh token from the backend to the client upon login. I have implemented the following FastAPI code to set a cookie:

```python
@app.post('/login', summary='Create access and refresh tokens for user', response_model=TokenSchema)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    ...

    response = JSONResponse({'access_token': create_access_token(user['id'])})
    response.set_cookie(key='refresh_token_test', value=create_refresh_token(user['id']),
                        max_age=REFRESH_TOKEN_EXPIRE_MINUTES, httponly=False, samesite='none', domain='http://localhost:3000')

    return response
```

On the client side, I am using Axios to send a login request:

```typescript
const onClickLogin = () => {
    axios({
      method: 'post',
      url: 'http://localhost:8000/login',
      responseType: 'json',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      data: {
        username: inputUsername(),
        password: inputPw(),
      },
    }).then((response) => {
      props.setToken(response.data.access_token);
      props.updateUserinfo();
      props.setPageStatus('loggedin');
    });
  };
```

I have disabled the 'httponly' option to check the cookie more easily in Chrome developer tools. Despite the response being received successfully without any errors or warnings, no cookies are present. I have configured CORS in FastAPI as follows:

```python
origins = [
    'http://localhost:3000'
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Why is the browser not receiving cookies, and how can I debug this issue?
```

**Flags:** Reporter cited: ['0.88.0', '3.10.5']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## fastapi/fastapi/issue/5831
**Title:** Fastapi 
**Repo:** fastapi/fastapi | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### First Check

- [X] I added a very descriptive title to this issue.
- [X] I used the GitHub search to find a similar issue and didn't find it.
- [X] I searched the FastAPI documentation, with the integrated search.
- [X] I already searched in Google "How to X in FastAPI" and didn't find any information.
- [X] I already read and followed all the tutorial in the docs and didn't find an answer.
- [X] I already checked if it is not related to FastAPI but to [Pydantic](https://github.com/samuelcolvin/pydantic).
- [X] I already checked if it is not related to FastAPI but to [Swagger UI](https://github.com/swagger-api/swagger-ui).
- [X] I already checked if it is not related to FastAPI but to [ReDoc](https://github.com/Redocly/redoc).

### Commit to Help

- [X] I commit to help with one of those options 👆

### Example Code

```python
from fastapi import FastAPI
import gradio as gr

CUSTOM_PATH = "/gradio"

app = FastAPI()

@app.get("/")
def read_main():
    return {"message": "Thi...
```

### Drafted eval_question
```
I am using FastAPI with Python 3.9 on Windows and have integrated a Gradio app into my FastAPI application. I want to restrict access to the '/gradio' path so that only logged-in users can access it. Can I implement a condition to check if a user is logged in and subscribed before allowing access? Here is the code I am currently using:

```python
from fastapi import FastAPI
import gradio as gr

CUSTOM_PATH = "/gradio"

app = FastAPI()

@app.get("/")
def read_main():
    return {"message": "This is your main app"}

io = gr.Interface(lambda x: "Hello, " + x + "!", "textbox", "textbox")
gradio_app = gr.routes.App.create_app(io)

app.mount(CUSTOM_PATH, gradio_app)
```
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## fastapi/fastapi/issue/5818
**Title:** TrustedHostMiddleware ignores port in Host header
**Repo:** fastapi/fastapi | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### First Check

- [X] I added a very descriptive title to this issue.
- [X] I used the GitHub search to find a similar issue and didn't find it.
- [X] I searched the FastAPI documentation, with the integrated search.
- [X] I already searched in Google "How to X in FastAPI" and didn't find any information.
- [X] I already read and followed all the tutorial in the docs and didn't find an answer.
- [X] I already checked if it is not related to FastAPI but to [Pydantic](https://github.com/samuelcolvin/pydantic).
- [X] I already checked if it is not related to FastAPI but to [Swagger UI](https://github.com/swagger-api/swagger-ui).
- [X] I already checked if it is not related to FastAPI but to [ReDoc](https://github.com/Redocly/redoc).

### Commit to Help

- [X] I commit to help with one of those options 👆

### Example Code

```python
app = FastAPI()
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost:8000"]
)
```


### Description

Using...
```

### Drafted eval_question
```
In FastAPI version 0.88.0, when using TrustedHostMiddleware with the allowed_hosts set to include a port, such as ['localhost:8000'], I receive an 'Invalid host header' response when making a request from localhost:8000. The browser sends the header as 'Host: localhost:8000'. However, if I change allowed_hosts to ['localhost'], it works fine. Is this behavior intended, or should the middleware accept the host with the port as specified in the Host header? Here is the example code:

```python
app = FastAPI()
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost:8000"]
)
```

I am running this on Linux with Python 3.10.8.
```

**Flags:** Reporter cited: ['0.88.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## fastapi/fastapi/issue/5723
**Title:** Using scopes on `Security()` changes dependency inheritance
**Repo:** fastapi/fastapi | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### First Check

- [X] I added a very descriptive title to this issue.
- [X] I used the GitHub search to find a similar issue and didn't find it.
- [X] I searched the FastAPI documentation, with the integrated search.
- [X] I already searched in Google "How to X in FastAPI" and didn't find any information.
- [X] I already read and followed all the tutorial in the docs and didn't find an answer.
- [X] I already checked if it is not related to FastAPI but to [Pydantic](https://github.com/samuelcolvin/pydantic).
- [X] I already checked if it is not related to FastAPI but to [Swagger UI](https://github.com/swagger-api/swagger-ui).
- [X] I already checked if it is not related to FastAPI but to [ReDoc](https://github.com/Redocly/redoc).

### Commit to Help

- [x] I commit to help with one of those options 👆

### Example Code

```python
async def get_authenticated_user(security_scopes: SecurityScopes,
                                 session: Session = Depends(get_session),
                ...
```

### Drafted eval_question
```
In FastAPI version 0.87.0, when using the `Security()` dependency with `scopes=["activate"]`, I observe that the session IDs for `get_authenticated_user` and `user_activate` are different, which is unexpected as I thought arguments propagate through dependencies. Without the scopes, the session IDs are the same. Here's the example code:

```python
async def get_authenticated_user(security_scopes: SecurityScopes,
                                 session: Session = Depends(get_session),
                                 token: str = Depends(oauth2_scheme),
                                 ):

    print(f"get_authenticated_user: {id(session)}")
    return

@router.post('/activate', status_code=204)
async def user_activate(session: Session = Depends(get_session),
                        user: UserAccountInDatabase = Security(
                            get_authenticated_user,
                            scopes=["activate"])):
    print(f"user_activate: {id(session)}")
    return
```

The output with scopes is:
```
get_authenticated_user: 140600933628496
user_activate: 140600933312848
```

Without scopes, the output is:
```
get_authenticated_user: 139952151843088
user_activate: 139952151843088
```

I also tried manually adding the security scopes, but it seems like `security_scopes` is empty, possibly overwritten. Is this behavior expected, or am I misunderstanding how `Security()` and `SecurityScopes` work in FastAPI?
```

**Flags:** Reporter cited: ['0.87.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## fastapi/fastapi/issue/5386
**Title:** "request.json()" hangs indefinitely in middleware
**Repo:** fastapi/fastapi | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
@csrgxtu I need to read the body in JSON format in several middleware in order to process the data for various reasons (logging, security, sanitizing, etc.) so I wonder what the correct implementation would be in order to avoid halting the program?
```

### Drafted eval_question
```
I am using FastAPI version 0.79.0 on Ubuntu 22.04 with Python 3.10.4. I have implemented a middleware using BaseHTTPMiddleware where I attempt to read the request body as JSON using `await request.json()`. However, when I run the application with `uvicorn main:app --reload` and send a POST request using CURL, the application hangs indefinitely and does not respond. This issue does not occur when using Starlette instead of FastAPI. Here is the code I am using:

```python
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

class Middleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        await request.json()
        response = await call_next(request)
        return response

app = FastAPI()
app.add_middleware(Middleware)

@app.post("/test")
async def test(test: dict) -> dict:
    return {"data": "test"}
```

How can I correctly read the JSON body in middleware for purposes such as logging, security, and sanitizing without causing the application to hang?
```

**Flags:** Reporter cited: ['0.79.0', '3.10.4']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## fastapi/fastapi/issue/5334
**Title:** Cookies Received, but doesn't stored inside the browser 
**Repo:** fastapi/fastapi | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### First Check

- [X] I added a very descriptive title to this issue.
- [X] I used the GitHub search to find a similar issue and didn't find it.
- [X] I searched the FastAPI documentation, with the integrated search.
- [x] I already searched in Google "How to X in FastAPI" and didn't find any information.
- [X] I already read and followed all the tutorial in the docs and didn't find an answer.
- [X] I already checked if it is not related to FastAPI but to [Pydantic](https://github.com/samuelcolvin/pydantic).
- [X] I already checked if it is not related to FastAPI but to [Swagger UI](https://github.com/swagger-api/swagger-ui).
- [X] I already checked if it is not related to FastAPI but to [ReDoc](https://github.com/Redocly/redoc).

### Commit to Help

- [X] I commit to help with one of those options 👆

### Example Code

### Description

tldr; get responses back from cookies, but it doesn't stored on the application, and still able to send it on every request.

I ha...
```

### Drafted eval_question
```
I am using FastAPI version 0.79.0 with a frontend framework using Svelte and Axios on Windows 11. I have implemented a login function where cookies are set when tested with Swagger UI, but when making requests from the frontend using Axios, the cookies are not stored in the browser's application tab, although they are sent with every request. Here is the relevant code:

Frontend (Svelte + Axios):

```javascript
async function onclick(e){
  axios.defaults.withCredentials = true;
  let info = {};
  const formData = new FormData(e.target);
  json = Object.fromEntries(formData.entries())
  await axios.post('http://127.0.0.1:8000/login', json,  { withCredentials: true} )
    .then(response =>(
      info = response.data
    )
    )
  
    if (info.status == "Success"){
      console.log("Hello")
    }
}
```

Backend (FastAPI):

```python
@router.post('')
def login(response : Response,request: schemas.Login, db: Session = Depends(database.get_db)):
    user = db.query(models.Users).filter(models.Users.email == request.email).first()
    if not user:
        return "User doesn't exist"
    if not Hash.verify(user.password,request.password):
        return "Incorrect Password"
    access_token = jwttoken.create_access_token(data={"sub": user.email, "id" : user.id})
    response.set_cookie(
        key="token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite='none',
    )
    return {"status": "Success", "token": access_token}
```

Middleware (CORS):

```python
origins = [
    "http://localhost",
    "http://localhost:3000",
]

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*']
    )
]

app = FastAPI(middleware=middleware)
```

I have tried setting `secure` to `False` and `samesite` to "Lax", but I still encounter issues. What could be causing the cookies not to be stored in the browser, and how can I resolve this?
```

**Flags:** Reporter cited: ['0.79.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## fastapi/fastapi/issue/5177
**Title:** response cookie values need use 'utf-8' encode
**Repo:** fastapi/fastapi | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### First Check

- [X] I added a very descriptive title to this issue.
- [X] I used the GitHub search to find a similar issue and didn't find it.
- [X] I searched the FastAPI documentation, with the integrated search.
- [X] I already searched in Google "How to X in FastAPI" and didn't find any information.
- [X] I already read and followed all the tutorial in the docs and didn't find an answer.
- [X] I already checked if it is not related to FastAPI but to [Pydantic](https://github.com/samuelcolvin/pydantic).
- [X] I already checked if it is not related to FastAPI but to [Swagger UI](https://github.com/swagger-api/swagger-ui).
- [X] I already checked if it is not related to FastAPI but to [ReDoc](https://github.com/Redocly/redoc).

### Commit to Help

- [X] I commit to help with one of those options 👆

### Example Code

```python
response.set_cookie(key=k, value=v, max_age=90 * 24 * 60 * 60)
  File "/xx/.local/lib/python3.8/site-packages/starlette/responses.py", line 132, in set_cooki...
```

### Drafted eval_question
```
In FastAPI version 0.78.0 running on Python 3.8.10 on Linux, I encountered a UnicodeEncodeError when setting a cookie using the set_cookie method. The error occurs because the method attempts to encode the cookie value using 'latin-1', which cannot encode certain characters. Here is the example code that triggers the error:

```python
response.set_cookie(key=k, value=v, max_age=90 * 24 * 60 * 60)
  File "/xx/.local/lib/python3.8/site-packages/starlette/responses.py", line 132, in set_cookie
    self.raw_headers.append((b"set-cookie", cookie_val.encode("latin-1")))
UnicodeEncodeError: 'latin-1' codec can't encode characters in position 18-19: ordinal not in range(256)
```

Is there a way to change the encoding to 'utf-8' for response cookie values, or is there a workaround for this issue?
```

**Flags:** Reporter cited: ['0.78.0', '3.8.10']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## fastapi/fastapi/issue/5017
**Title:** Connecting to database with Psycopg2 and FastAPI Routers
**Repo:** fastapi/fastapi | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
Hey @BenL-github, sorry this doesn't answer your question&mdash;and I'm asking one of my own instead: is your API to interact with external users? If so, how do you plan on handling sql injection? Even though I'm more comfortable with psycopg2 for Postgres CRUD than an ORM, I feel like SQLAlchemy offers more of a "plug-and-play" approach to defend vs sql injection (vs mannually sanitizing queries in psycopg2). I'm having this dilemma right now...
```

### Drafted eval_question
```
I am using FastAPI version 0.78.0 on macOS with Python 3.8.9, and I have implemented a database connection using psycopg2. My setup involves a Database class in main.py that connects to the database, and I import this into each route to access the database object. This seems to create a circular dependency because main imports test_route, and test_route imports main. However, uvicorn does not seem to be affected by this. Is this the best way to handle database connections with psycopg2 and FastAPI routers, or is there a better approach to avoid circular dependencies?
```

**Flags:** Reporter cited: ['0.78.0', '3.8.9']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## fastapi/fastapi/issue/4990
**Title:** Trailing backslash reruns makes a redirect that looses https.
**Repo:** fastapi/fastapi | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### First Check

- [X] I added a very descriptive title to this issue.
- [X] I used the GitHub search to find a similar issue and didn't find it.
- [X] I searched the FastAPI documentation, with the integrated search.
- [X] I already searched in Google "How to X in FastAPI" and didn't find any information.
- [X] I already read and followed all the tutorial in the docs and didn't find an answer.
- [X] I already checked if it is not related to FastAPI but to [Pydantic](https://github.com/samuelcolvin/pydantic).
- [X] I already checked if it is not related to FastAPI but to [Swagger UI](https://github.com/swagger-api/swagger-ui).
- [X] I already checked if it is not related to FastAPI but to [ReDoc](https://github.com/Redocly/redoc).

### Commit to Help

- [X] I commit to help with one of those options 👆

### Example Code

```python
application = FastAPI()

application.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
...
```

### Drafted eval_question
```
I am using FastAPI version 0.78.0 with CORS middleware on a Linux system and Python 3.8.10. I noticed that when a URL with a trailing backslash is accessed, it results in a 307 Temporary Redirect. This behavior is expected with an HTTP URL, but when using an HTTPS URL, the redirect changes HTTPS to HTTP, which is not expected. This issue is causing confusion as the endpoint does not respond correctly. The SSL certificate used is self-signed. Is this behavior a security vulnerability or a bug in FastAPI?
```

**Flags:** Reporter cited: ['0.78.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## fastapi/fastapi/issue/4962
**Title:** jsonable_encoder alters json_encoders of Pydantic objects
**Repo:** fastapi/fastapi | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### First Check

- [X] I added a very descriptive title to this issue.
- [X] I used the GitHub search to find a similar issue and didn't find it.
- [X] I searched the FastAPI documentation, with the integrated search.
- [X] I already searched in Google "How to X in FastAPI" and didn't find any information.
- [X] I already read and followed all the tutorial in the docs and didn't find an answer.
- [X] I already checked if it is not related to FastAPI but to [Pydantic](https://github.com/samuelcolvin/pydantic).
- [X] I already checked if it is not related to FastAPI but to [Swagger UI](https://github.com/swagger-api/swagger-ui).
- [X] I already checked if it is not related to FastAPI but to [ReDoc](https://github.com/Redocly/redoc).

### Commit to Help

- [X] I commit to help with one of those options 👆

### Example Code

```python
from pydantic import BaseModel, SecretStr
from fastapi.encoders import jsonable_encoder


class Credentials(BaseModel):
    password: SecretStr


ENCO...
```

### Drafted eval_question
```
I'm using FastAPI version 0.78.0 with Pydantic version 1.9.1 on Linux, and I've encountered an issue with the `jsonable_encoder` function. When I use `jsonable_encoder` with a `custom_encoder`, it seems to modify the `__config__.json_encoders` of Pydantic objects, affecting subsequent calls to `jsonable_encoder` without a `custom_encoder`. This results in sensitive data, such as passwords, being exposed in API responses. Here's a code example demonstrating the issue:

```python
from pydantic import BaseModel, SecretStr
from fastapi.encoders import jsonable_encoder


class Credentials(BaseModel):
    password: SecretStr


ENCODERS = {SecretStr: lambda v: v.get_secret_value() if v is not None else None}

creds = Credentials(password="helloworld")

a = jsonable_encoder(creds)
print(a)  # {'password': '**********'}, as expected
b = jsonable_encoder(creds, custom_encoder=ENCODERS)
print(b)  # {'password': 'helloworld'}, as expected
c = jsonable_encoder(creds)
print(c)  # gives {'password': 'helloworld'}, but should be {'password': '**********'}?


creds = Credentials(password="123456789")

d = jsonable_encoder(creds)
print(d)  # gives {'password': '123456789'}, but should be {'password': '**********'}?
```

Is this behavior a genuine security vulnerability in FastAPI, and how can I ensure that `custom_encoder` only affects the current call without altering global state?
```

**Flags:** Reporter cited: ['0.78.0', '1.9.1']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## fastapi/fastapi/issue/4946
**Title:** default HTTPException handler adds content when there should be none
**Repo:** fastapi/fastapi | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### First Check

- [X] I added a very descriptive title to this issue.
- [X] I used the GitHub search to find a similar issue and didn't find it.
- [X] I searched the FastAPI documentation, with the integrated search.
- [X] I already searched in Google "How to X in FastAPI" and didn't find any information.
- [X] I already read and followed all the tutorial in the docs and didn't find an answer.
- [X] I already checked if it is not related to FastAPI but to [Pydantic](https://github.com/samuelcolvin/pydantic).
- [X] I already checked if it is not related to FastAPI but to [Swagger UI](https://github.com/swagger-api/swagger-ui).
- [X] I already checked if it is not related to FastAPI but to [ReDoc](https://github.com/Redocly/redoc).

### Commit to Help

- [X] I commit to help with one of those options 👆

### Example Code

```python
from fastapi import FastAPI, HTTPException
from starlette.requests import Request

app = FastAPI()

@app.get('/foo')
async def route(r...
```

### Drafted eval_question
```
In FastAPI version 0.78.0 running on Python 3.8.12, I encountered an issue where the default HTTPException handler seems to add content to responses for status codes like 304, where no content should be present. When I raise an HTTPException with status code 304 in my FastAPI application, an error is logged indicating 'Too much data for declared Content-Length'. Here is the code I used:

```python
from fastapi import FastAPI, HTTPException
from starlette.requests import Request

app = FastAPI()

@app.get('/foo')
async def route(request: Request):
    raise HTTPException(status_code=304)


def main():
    import uvicorn

    uvicorn.run(app, debug=True, host="0.0.0.0", port=8888,)


if __name__ == "__main__":
    main()
```

Is this behavior a genuine issue with FastAPI's handling of HTTPExceptions for status codes that should not have a response body?
```

**Flags:** Reporter cited: ['0.78.0', '3.8.12']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## fastapi/fastapi/issue/4833
**Title:** Do we solely rely on memory management to call UploadFile.close?
**Repo:** fastapi/fastapi | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
@jgould22 thanks for taking the time.

I'm afraid this does not answer my question entirely. I might not have been very clear. Let's try again!

I am aware of how UploadFile is implemented in FastAPI and in Starlette. My question is about how memory/disk space is managed when it comes down to using `UploadFile`. Starlette also is not calling `close()` explicitly in its code.

Maybe this example can illustrate my question a bit better: I am uploading a huge file (~1gb). Since all of this is using `SpooledTemporaryFile` internally, the upload should be written to disk right away. 
Usually in Python, once you are done processing, you would call `close()` on that file. This in turn would free up the disk space used.

Now I can't find any place where this `.close()` is called. Is that right? 

If there is no such place, the `close()` is probably called somewhere implicitly? Is it in memory management?

I guess my question is: where is the space (in memory or on disk) freed?
```

### Drafted eval_question
```
In FastAPI version 0.75.1, when handling file uploads using the UploadFile class, why do the documentation examples not explicitly call `await file.close()`? In typical Python file handling, one would use a try/finally block or a context manager to ensure files are closed properly, as shown in the examples below:

```python
# pre-context manager style
try:
    img = open("me.png", "rb")
    # do something with it that might error out
    print(img)
finally:
    img.close()

# or the new style
with open("me.png", "rb") as img:
    # process. img.close() called by context manager when leaving block.
    print(img)
```

However, the FastAPI documentation does not show a similar pattern for UploadFile, such as:

```python
from fastapi import FastAPI, File, UploadFile

app = FastAPI()

@app.post("/uploadfile/")
async def create_upload_file(file: UploadFile):
    try:
        name = file.filename
    finally:
        file.close()
    return {"filename": name}
```

Is there a risk of memory or file descriptor leakage if `UploadFile.close()` is not explicitly called within the endpoint? Does Python's memory management handle this automatically, or should developers manually ensure that `close()` is called to free up resources, especially when dealing with large files? I am using macOS 11.6.5 and macOS 12.3.1 with Python 3.9.10.
```

**Flags:** Reporter cited: ['0.75.1']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## fastapi/fastapi/issue/4768
**Title:** Securing routes with Firebase Auth access token
**Repo:** fastapi/fastapi | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
One more question: Is there any way to computationally turn Bearer auth on/off?

I tried to do it inside the authentication methods, but if no token is passed, a `403 error` is returned before these are even executed.
```

### Drafted eval_question
```
I am using FastAPI version 0.75.1 on Linux with Python versions 3.7 to 3.10. I have a frontend that authenticates with Firebase Auth and receives a bearer token, which is then sent to the backend. For certain routes, I want to check for both authentication and authorization. I need to extract the token from the header and verify it using the Firebase Admin library, and then check the custom claims against a list of authorized claims. How do I create appropriate dependency injection functions in FastAPI to perform these checks? Additionally, is there a way to configure HTTPBearer so that the OpenAPI docs infer the required header, and can I computationally turn Bearer auth on/off?
```

**Flags:** Reporter cited: ['0.75.1', '3.7', '3.10']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## pyca/cryptography/issue/14709
**Title:** Hashing files in Python using cryptography (the module)?
**Repo:** pyca/cryptography | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
I'm new to cryptography (both the module and the area of knowledge), and I'd humbly ask for anyone more knowledgeable with this module than me to give me some instructions for how to create a separate hash/signature of a file. That's all. Since there's no discussion board in GitHub (to the best of my knowledge), this is the best I can do as far as asking a question. It's less an issue with the module and more my lack of knowledge on its capabilities.
```

### Drafted eval_question
```
How can I use the 'cryptography' module in Python to create a separate hash or signature of a file? I am new to both the module and the field of cryptography and would appreciate guidance on this process.
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## pyca/cryptography/issue/14690
**Title:** Tracking: Post-quantum cryptography (ML-KEM / ML-DSA / SLH-DSA) support roadmap
**Repo:** pyca/cryptography | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Hey all,

First — I know this library *implements* RSA and ECC. That's the point. 
This isn't a "you have vulnerabilities" issue. It's more of a "where are 
we on PQC support and can I help" issue.

Context: I've been building a scanner (QuantumMigrate) that audits 
codebases for quantum-vulnerable crypto usage. I ran it on this repo 
mostly out of curiosity, and it flagged 174 usages in src/ alone — which 
is completely expected given what this library does. But it made me 
wonder about the roadmap for NIST PQC support.

NIST finalized three standards in 2024:
- ML-KEM (FIPS 203) — key encapsulation, replaces RSA/DH/ECDH
- ML-DSA (FIPS 204) — signatures, replaces RSA/ECDSA/DSA  
- SLH-DSA (FIPS 205) — hash-based signatures, conservative backup

The deadline pressure is real. "Harvest now, decrypt later" means 
encrypted data being sent over TLS today is potentially being stockpiled. 
The sensitive stuff — healthcare records, financial transactions, anything 
with a long confidentialit...
```

### Drafted eval_question
```
What is the roadmap for post-quantum cryptography (PQC) support in the pyca/cryptography library, specifically regarding the implementation of NIST's finalized standards ML-KEM, ML-DSA, and SLH-DSA? I am interested in understanding if there are plans to integrate these standards, especially considering OpenSSH's experimental support for ML-KEM-768 and OpenSSL 3.5's post-quantum support. Additionally, is there any intention to deprecate the use of SHA1 and MD5 for signing in the OID signature algorithm map? How can I contribute to this effort, particularly if OpenSSL exposes PQC primitives?
```

**Flags:** Reporter cited: ['FIPS 203', 'FIPS 204', 'FIPS 205', 'OpenSSH 9.0', 'OpenSSL 3.5']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## pyca/cryptography/issue/14207
**Title:** Rust once_cell dependency has CVE-2019-16141 vulnerability
**Repo:** pyca/cryptography | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Now cryptography has Cargo.toml file where `once_cell` declared as version "1":

```
[dependencies]
...
once_cell = "1"
```

which is reported by some vulnerability scanners as CVE-2019-16141 (https://nvd.nist.gov/vuln/detail/CVE-2019-16141)

The latest once_cell version is [v1.21.3](https://github.com/matklad/once_cell/releases/tag/v1.21.3)

This issue is about to bump once_cell to latest version to close CVE-2019-16141 and keep once_cell up-to-date.

```

### Drafted eval_question
```
The cryptography library's Cargo.toml file declares a dependency on `once_cell` version "1", which is flagged by some vulnerability scanners as having CVE-2019-16141. The latest version of `once_cell` is v1.21.3. Should the `once_cell` dependency be updated to the latest version to address this vulnerability?
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2019-16141'] | NEEDS REVIEW | Reporter cited: ['CVE-2019-16141', 'v1.21.3']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## pyca/cryptography/issue/14013
**Title:** unable to load encrypted RSA key with cryptography 46.0.3 - ASN.1 parsing error: unexpected tag
**Repo:** pyca/cryptography | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
I think I am encountering the same issue as https://github.com/pyca/cryptography/issues/13045
Unable to read encrypted RSA keys in the traditional PEM format, even the ones I just saved.

```
>>> cryptography.__version__
'46.0.3'
>>> paramiko.__version__
'2.12.0'

khomenko@nihao$ openssl genrsa -out test.key -traditional
khomenko@nihao$ cat test.key
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAyXGVAo1GwTFjpHOp4AAO0z4QiOHs5Ip9WIxiko4Bx32lN/cQ
zHeCnaDd8NpNSRuBSR1P/tUgFoft21Xiv/biDlYZ0vtClNmPN7AN755/9C55S/nN
kNfebIPlnGTmqglZCrFcH899rYk8GRF+wT1S0EuwZiKQ/oKjmODKxggZmF27+WpW
irDIcyKHA6FkHjghMRQSmxlHuTLEZQoYQwC9HYxFr38MZrWAebzEztqTbfgHD9Di
BVcIrQQ83fdeMYEJrH2i8d8mnYfqikzXEccMlv6hX1K4F+8z3gzqSmvWZhpRl1Jw
RRSIWcs5VmkKmF8z1z2q/FfL+43TMcbtuJmwNwIDAQABAoIBAGJAiPpWp+UAzuXe
GEQOIyz7P5tT/nQ17A8tYcKzisCfUt9qHQJtZAK3/KhGAZ4f0T41EthrYRw8LlJl
oJQauYVej3ftXzs0pfr2XsW53BTgOf9Jlu8Hqw/ogSx3tl3G82wYt6M4U8c5gVuE
wftEisjXsfEO+QN5+otNUPmn57v9VltwD7bBzcJP/3bRqSH8M7Strp2SX+H7qhmq
Ifknn14WZfj65AvPoWtmVF59IU6ayWw...
```

### Drafted eval_question
```
(ERROR — see eval_questions.jsonl)
```

**Flags:** NEEDS REVIEW | ERROR: LLM returned non-JSON: {
  "eval_question": "I am experiencing an issue with cryptography version 46.0.3 where I am unable to load encrypted RSA keys in the traditional PEM format. I generated an RSA key using OpenSSL and attempted to read and write it using Paramiko version 2.12.0, but encountered an ASN.1 parsing error 

**Approved:** [ ] (set `approved:true` in JSONL)

---

## pyca/cryptography/issue/13843
**Title:** `Name.rfc4514_string` emits non-parseable output for trailing spaces
**Repo:** pyca/cryptography | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
I want to clarify, do you believe this is an issue with `rfc4514_string` or `from_rfc4514_string`?

You say:
> When an attribute value ends with a space, Name.rfc4514_string() escapes it incorrectly.

However, you also say:
> RFC 4514 requires trailing spaces to be escaped as `\`

Which is what it seems to be doing.

Therefore, it looks to me like the issue is that we don't parse it, not that what we generate is invalid.
```

### Drafted eval_question
```
Is the behavior of `Name.rfc4514_string()` in the `cryptography` library version 46.0.3 a security vulnerability or bug when it emits non-parseable output for attribute values ending with a space? Specifically, when an attribute value ends with a space, `Name.rfc4514_string()` escapes it as `\ `, which `Name.from_rfc4514_string()` cannot parse, breaking the round-trip guarantee. This could affect applications relying on round-tripping, such as certificate tooling or directory synchronization, and could potentially lead to unexpected crashes if a crafted DN from untrusted input is processed. Here is a code example demonstrating the issue:

```python
from cryptography.x509 import Name
from cryptography.x509.name import NameAttribute
from cryptography.x509.oid import NameOID

name = Name([NameAttribute(NameOID.COMMON_NAME, "0"),
             NameAttribute(NameOID.ORGANIZATION_NAME, " ")])
s = name.rfc4514_string()          # yields "CN=0,O=\\ "
Name.from_rfc4514_string(s)        # raises ValueError
```

Traceback:
```
Traceback (most recent call last):
  File "/data/src/test.py", line 8, in <module>
    Name.from_rfc4514_string(s)        # raises ValueError
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/py312/lib/python3.12/site-packages/cryptography/x509/name.py", line 316, in from_rfc4514_string
    return _RFC4514NameParser(data, attr_name_overrides or {}).parse()
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/py312/lib/python3.12/site-packages/cryptography/x509/name.py", line 442, in parse
    self._read_char(",")
  File "/home/py312/lib/python3.12/site-packages/cryptography/x509/name.py", line 415, in _read_char
    raise ValueError
ValueError
```

Does this behavior align with RFC 4514, and should it be considered a bug or security issue?
```

**Flags:** Reporter cited: ['46.0.3']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## pyca/cryptography/issue/13538
**Title:** Problem with an EC private key and load_der_private_key()
**Repo:** pyca/cryptography | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Hello,

I have discovered a case where a private key was loaded correctly in version 44.0.3, and is no more in version 45.0.0

After analysing the key, it is a bit weird, with some supplemental useless "padding" bytes at the end. I do not have the creation history of these data, if it has been with a specific openssl version or not ...
Here is small code showing the problem (tested in a virtual env with both versions). The "good" version works fine for both, the "bad" one works with 44.0.3, and fails with 45.0.0

```
cryptography.hazmat.primitives.serialization import load_der_private_key
# good key for all versions
der_key = bytes.fromhex("3041020100301306072a8648ce3d020106082a8648ce3d0301070427302502010104201445af4b5ea31dfc2043e41b527a78b0feed297bd367ff92920e80efc910eba8")

# bad key for version 45.0.0 and beyond
der_key = bytes.fromhex("3041020100301306072a8648ce3d020106082a8648ce3d0301070427302502010104201445af4b5ea31dfc2043e41b527a78b0feed297bd367ff92920e80efc910eba800000000000000...
```

### Drafted eval_question
```
I have encountered an issue where a private key that was successfully loaded using the `load_der_private_key()` function in version 44.0.3 of the pyca/cryptography library is no longer loading in version 45.0.0. The key has some additional padding bytes at the end. Here is a code snippet demonstrating the problem:

```
cryptography.hazmat.primitives.serialization import load_der_private_key
# good key for all versions
der_key = bytes.fromhex("3041020100301306072a8648ce3d020106082a8648ce3d0301070427302502010104201445af4b5ea31dfc2043e41b527a78b0feed297bd367ff92920e80efc910eba8")

# bad key for version 45.0.0 and beyond
der_key = bytes.fromhex("3041020100301306072a8648ce3d020106082a8648ce3d0301070427302502010104201445af4b5ea31dfc2043e41b527a78b0feed297bd367ff92920e80efc910eba800000000000000000000000000")
print(der_key.hex())
try:
    key = load_der_private_key(der_key, password=None)
    print("the key is decoded")
except:
    print("the key cannot be decoded")
```

I am using Python version 3.12.3 on an Ubuntu 24.04 x86-64 machine. Additionally, I found similar issues with keys generated using OpenSSL. For example, a key generated with `openssl genrsa 2048` cannot be loaded, while one generated with `openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out key.pem` can be recognized. This seems related to the presence of an empty field (05 00). Can you provide any insights into why this change occurred between versions 44.0.3 and 45.0.0, and whether it is expected behavior?
```

**Flags:** Reporter cited: ['44.0.3', '45.0.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/9600
**Title:** Thread-safety: data race in ImagingDefaultArena block cache (memory_get_block / memory_return_block)
**Repo:** python-pillow/Pillow | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### What did you do?

Used `asyncio.to_thread()` / `ThreadPoolExecutor` to offload PIL Image operations (create, load, resize, encode) to multiple threads concurrently.

### What did you expect to happen?

Thread-safe access to PIL Image allocation/deallocation, or documentation stating that multi-threaded usage requires `set_blocks_max(0)`.

### What actually happened?

`ImagingDefaultArena` in `src/libImaging/Storage.c` uses shared mutable state (`blocks_cached`, `blocks_pool`) without any synchronization. When multiple threads call `memory_get_block` / `memory_return_block` concurrently (which happens when PIL's GIL-releasing C operations run in parallel), data races can occur:

```c
// memory_get_block (line 310) — no lock
if (arena->blocks_cached > 0) {
    arena->blocks_cached -= 1;                          // ← read-modify-write, no lock
    block = arena->blocks_pool[arena->blocks_cached];   // ← concurrent read, no lock
}

// memory_return_block (line 347) — no lock
if (arena-...
```

### Drafted eval_question
```
Is the behavior of data races in the ImagingDefaultArena block cache a genuine security vulnerability in Pillow 10.4.0 when using asyncio.to_thread() or ThreadPoolExecutor for concurrent PIL Image operations? Specifically, does the lack of synchronization in memory_get_block and memory_return_block functions lead to potential memory management issues such as use-after-free or double-free risks? How should this be addressed in a multi-threaded environment on Linux x86_64 with Python 3.12?
```

**Flags:** Reporter cited: ['10.4.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/9579
**Title:** Bundled libtiff 4.7.1 is vulnerable to CVE-2026-4775 (integer overflow in putcontig8bitYCbCr44tile)
**Repo:** python-pillow/Pillow | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
If this is a high severity problem, then do you know why libtiff hasn't released a new version to address it?
```

### Drafted eval_question
```
Pillow versions 12.1.1 and 12.2.0 bundle libtiff 4.7.1, which is vulnerable to CVE-2026-4775 due to a signed integer overflow in the function `putcontig8bitYCbCr44tile` in `tif_getimage.c`. This vulnerability can lead to an out-of-bounds heap write when processing a specially crafted TIFF file, potentially causing denial of service or arbitrary code execution. The bundled libtiff in Pillow ignores the system library, so upgrading the system libtiff does not mitigate the issue. The vulnerability is confirmed in the official libtiff 4.7.1 tarball, and the fix was committed after the release of 4.7.1. Should the vendored libtiff in Pillow be updated to include the fix from commit `782a11d6`, or should a patch be applied to the current version before the next build?
```

**Flags:** Reporter cited: ['CVE-2026-4775', '782a11d6']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/9439
**Title:** Security fix for Pillow 11.3
**Repo:** python-pillow/Pillow | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Could it be possible to merge the security fix for [CVE-2026-25990](https://github.com/python-pillow/Pillow/security/advisories/GHSA-cfh3-3jmp-rvhc) to 11.3 and release a patch version there?
Reason is that the ecosystem, I am working in, is stuck on Python 3.9 for a while.
```

### Drafted eval_question
```
Could it be possible to merge the security fix for CVE-2026-25990 to Pillow version 11.3 and release a patch version? The ecosystem I am working in is stuck on Python 3.9 for a while.
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2026-25990'] | NEEDS REVIEW | Reporter cited: ['CVE-2026-25990']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/9361
**Title:** Segfaults when using the 39C3 font from Chaos Communication congress
**Repo:** python-pillow/Pillow | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
<!--
Thank you for reporting an issue.

Follow these guidelines to ensure your issue is handled properly.

If you have a ...

1.  General question: consider asking the question on Stack Overflow
    with the python-imaging-library tag:

    * https://stackoverflow.com/questions/tagged/python-imaging-library

    Do not ask a question in both places.

    If you think you have found a bug or have an unexplained exception
    then file a bug report here.

2.  Bug report: include a self-contained, copy-pastable example that
    generates the issue if possible. Be concise with code posted.
    Guidelines on how to provide a good bug report:

    * https://stackoverflow.com/help/mcve

    Bug reports which follow these guidelines are easier to diagnose,
    and are often handled much more quickly.

3.  Feature request: do a quick search of existing issues
    to make sure this has not been asked before.

We know asking good questions takes effort, and we appreciate your time.
Thank you.
-->...
```

### Drafted eval_question
```
I am experiencing a segmentation fault (SIGSEGV) when trying to list the styles of the 'Kario39C3Var-Roman.ttf' font from the 39C3 Design Package using Pillow 12.0.0 on Python 3.14.2. This occurs on both a python3-slim Docker image on Ubuntu 24.04.3 LTS running on WSL2 and natively. Here is the code I used:

```python
#!/usr/bin/env python3

from PIL import ImageFont
import pprint

font = ImageFont.truetype('Kario39C3Var-Roman.ttf')
pprint.pp(font.get_variation_names())
```

Could this be a security issue related to a Null Pointer Exception, and how can it be resolved?
```

**Flags:** Reporter cited: ['12.0.0', '3.14.2']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/9295
**Title:** 12.0.0 release was re-tagged / re-created?
**Repo:** python-pillow/Pillow | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Hello,

When downloading upstream sources for packaging purposes, we are "locking" them via a checksum mechanism.  
We do this to ensure that sources have not been tampered with since the first build of the package, as well as for reproducible builds purposes.

We have identified that the `pillow` source's checksum for the `12.0.0` release have changed since the first time we built the related package, which might indicate that said release has either been tampered with or got re-tagged / re-created, which seems to be confirmed by the fact that we have [first built the package](https://gitlab.archlinux.org/archlinux/packaging/packages/python-pillow/-/commit/b5de721512f9833c4b5e25279b24185b575394d4) for the `12.0.0` release at October 15, 2025 at 2:35 PM GMT+2, while the latest [12.0.0 tag](https://github.com/python-pillow/Pillow/tags) was (re-?)created at October 15, 2025 at 7:06 PM GMT+2.

Can you confirm if the `12.0.0` release was re-tagged / re-created?
If so, can we safely update ...
```

### Drafted eval_question
```
We have identified that the checksum for the `pillow` source's `12.0.0` release has changed since we first built the related package. This suggests that the release may have been tampered with or re-tagged/re-created. We initially built the package for the `12.0.0` release on October 15, 2025, at 2:35 PM GMT+2, while the latest `12.0.0` tag was created at October 15, 2025, at 7:06 PM GMT+2. Can you confirm if the `12.0.0` release was re-tagged or re-created? If so, can we safely update our `pillow` package to the new source for the `12.0.0` release? Additionally, if the re-tag/re-creation was intentional, would it be possible to create a new point release instead of re-creating the same release in the future?
```

**Flags:** Reporter cited: ['12.0.0', 'b5de721512f9833c4b5e25279b24185b575394d4']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/9101
**Title:** Consider adopting an image-format-per-plugin model
**Repo:** python-pillow/Pillow | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Pillow's current model of *all image formats in one package* means that Pillow's footprint will inevitably grow boundlessly. The 10.1.0 Linux wheels were ~3.5MB, 10.2.0 went up to 4.5MB then 11.3.0 jumped all the way up to ~6.5MB for AVIF support (and these are compressed sizes – the installed footprint is worse). For anyone not using the new image formats and where a small footprint is coveted (serverless lambdas, small end user applications, services shipped as Docker images), every new addition is also a large regression.

From a security perspective, a new unneeded format is also a choice between an increased surface area of attack or squatting on old versions of Pillow – both of which are obviously bad. (Being able to limit formats using `Image.open(untrusted_content, formats=["JPEG", "PNG"])` helps but it's not really enough that I'd feel comfortable ignoring a CVE in `libavif`.)

I'm aware that pillow can be built without support for some formats by building from source or just ...
```

### Drafted eval_question
```
Would you consider adopting a policy whereby all new, large, niche, or complex image formats are permanently kept as separately distributed `pillow_$format_plugin` wheels rather than being merged into the main Pillow package? This would help manage the growing footprint of Pillow, which has increased significantly with recent versions due to added format support, and address security concerns by reducing the attack surface for users who do not need certain formats.
```

**Flags:** Reporter cited: ['10.1.0', '10.2.0', '11.3.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/8546
**Title:** Security concerns when loading user-provided fonts: Can they contain malware?
**Repo:** python-pillow/Pillow | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Hello! I have a question regarding the security of using user-provided fonts in Pillow.

I'm implementing a feature where a font uploaded by a user is loaded as a byte stream and then used in `ImageFont.truetype`. The loading and usage look like this:

```python
font_22 = None

if creator_profile.quote_font_file_id is not None:
    downloaded_font = await pl.app.backend._get_file(creator_profile.quote_font_file_id)
    if downloaded_font:
        font_22 = ImageFont.truetype(BytesIO(downloaded_font.content), 22)
```

My question:
How safe is it to accept fonts as byte streams and load them through ImageFont.truetype? Is there a risk that malicious fonts could contain viruses or otherwise disrupt the application? Are there any known vulnerabilities with font handling in Pillow or best practices for validating fonts before use?

Thank you very much in advance for any guidance!
```

### Drafted eval_question
```
How safe is it to accept fonts as byte streams and load them through ImageFont.truetype in Pillow? Is there a risk that malicious fonts could contain viruses or otherwise disrupt the application? Are there any known vulnerabilities with font handling in Pillow or best practices for validating fonts before use?

Code example:

```python
font_22 = None

if creator_profile.quote_font_file_id is not None:
    downloaded_font = await pl.app.backend._get_file(creator_profile.quote_font_file_id)
    if downloaded_font:
        font_22 = ImageFont.truetype(BytesIO(downloaded_font.content), 22)
```
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/8405
**Title:** Unused code in FliDecode.c and _imaging.c has SAST security issue
**Repo:** python-pillow/Pillow | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Hello!

According to the comments in _imaging.c thers is number of codecs, that must be replaced in PIL 1.2. But PIL development was discontinued 15 years ago.

![image](https://github.com/user-attachments/assets/2408b9f2-1603-4cc5-beb7-494b9b0119f2)

One of this codecs has SAST security issue.

![image](https://github.com/user-attachments/assets/ec52aefc-6ecd-4268-8524-b47aeaa5b22f)

`state->xsize` potentially be equal to zero, which will lead to division by zero exception in `ImagingFliDecode`. If this code is not used, I suggest remove it.

Found by Linux Verification Center (linuxtesting.org) with SVACE.
Reporter: Dmitriy Karasovsky ([d.karasovsky@fobos-nt.ru](mailto:d.karasovsky@fobos-nt.ru)).
```

### Drafted eval_question
```
In the Pillow library, specifically in the _imaging.c file, there is a codec that was supposed to be replaced in PIL 1.2. This codec has a SAST security issue where `state->xsize` can potentially be zero, leading to a division by zero exception in `ImagingFliDecode`. Since PIL development was discontinued 15 years ago, should this unused code be removed to address the security concern?
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/8073
**Title:** Why do Pillow's wheels put shared objects in the non-standard `.dylibs` directory on macOS (and thereby break code-signing without tons of additional support code)?
**Repo:** python-pillow/Pillow | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
I am opening this issue with a relatively low level of information because investigating what exactly is going on with all the build scripts is a fair amount of work, and someone more familiar with that system might be able to fill in the blanks far more quickly than I could. However, if the report is not clear, I can put in the effort to do a more substantive investigation and produced detailed error logs; I assume I'll have to do *some* of that but given how time-consuming and expensive it is to build a minimal code-signable app that can produce the relevant errors, I'd rather react to specific questions than try to have everything ready before filing a report.


<!--
Thank you for reporting an issue.

Follow these guidelines to ensure your issue is handled properly.

If you have a ...

1.  General question: consider asking the question on Stack Overflow
    with the python-imaging-library tag:

    * https://stackoverflow.com/questions/tagged/python-imaging-library

 ...
```

### Drafted eval_question
```
Why do Pillow's wheels place shared objects in the non-standard `.dylibs` directory on macOS, which causes issues with code-signing? I attempted to code-sign a macOS application using Pillow and found that the dylibs were located inside a zip file rather than in standard locations, leading to notarization failure. This requires additional support code as detailed in https://github.com/glyph/Encrust/issues/5. Is this behavior expected, and is it related to Pillow or another tool like `cibuildwheel`?
```

**Flags:** Reporter cited: ['Pillow 10.3.0', 'Python 3.11.9']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/7876
**Title:** Uncaught Exception(s) in Pillow Library
**Repo:** python-pillow/Pillow | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### What did you do?

We (@DogukanK, @esraercann) discovered a 3 crashes in Python Pillow library because of 'Uncaught Exception' via specially crafted input. 

### What did you expect to happen?

Exceptions should be handled properly in Pillow.

### What actually happened?

Crash. 

* Here is the first crash log:

 ```bash
=== Uncaught Python exception: ===

error: argument out of range

Traceback (most recent call last):

  File "/home/ubuntu/targets/pillow/main.py", line 20, in TestOneInput

    pilfuzz(data)

  File "/home/ubuntu/targets/pillow/main.py", line 11, in pilfuzz

    out = im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

  File "/home/ubuntu/.local/lib/python3.10/site-packages/PIL/Image.py", line 2807, in transpose

    def transpose(self, method):

  File "/home/ubuntu/.local/lib/python3.10/site-packages/PIL/ImageFile.py", line 266, in load

    err_code = decoder.decode(b"")[1]

  File "/home/ubuntu/.local/lib/python3.10/site-package...
```

### Drafted eval_question
```
(ERROR — see eval_questions.jsonl)
```

**Flags:** NEEDS REVIEW | ERROR: LLM returned non-JSON: {
  "eval_question": "We discovered three crashes in the Python Pillow library version 10.2.0 on Ubuntu 22.04.3 LTS with Python 3.10.12 due to 'Uncaught Exception' errors when processing specially crafted input. The exceptions are not being handled properly, leading to crashes. Here are the details 

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/7626
**Title:** Is Pillow affected by WebP vulnerability?
**Repo:** python-pillow/Pillow | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Being aware that CVE-2023-4863 was already fixed in Pillow 10.0.1 and as I'm unable to update to that version at the moment, I want to understand if Pillow really uses any of the functionality where the issue resides or if the CVE can be whitelisted since use of this vulnerable library is excluded by the functional design of Pillow.

Thank you

### What are your OS, Python and Pillow versions?

* OS: 
* Python: 
* Pillow:  < 10.0.1


```

### Drafted eval_question
```
Is Pillow affected by CVE-2023-4863, and can this CVE be safely whitelisted if the vulnerable functionality is not used by Pillow's design? I am currently unable to update to Pillow 10.0.1, where this issue is reportedly fixed.
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2023-4863', 'cve_ids:10.0.1', 'fixed_versions:10.0.1'] | NEEDS REVIEW | Reporter cited: ['CVE-2023-4863', '10.0.1']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/7518
**Title:** May I ask if Pillow 9.3.0 (windows) involves the CVE-2023-45853 vulnerability in zlib?
**Repo:** python-pillow/Pillow | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
windows 10
pillow 9.3.0
zlib 1.2.13

https://nvd.nist.gov/vuln/detail/CVE-2023-45853
![image](https://github.com/python-pillow/Pillow/assets/121840033/70916e66-503f-4e8f-ad14-edbc332a0692)
I don’t know if minizip related modules are involved.
```

### Drafted eval_question
```
Does Pillow 9.3.0 on Windows 10 involve the CVE-2023-45853 vulnerability in zlib 1.2.13? I am unsure if minizip related modules are involved.
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2023-45853'] | NEEDS REVIEW | Reporter cited: ['CVE-2023-45853']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/7179
**Title:** LibTIFF vulnerability (CVE-2023-30774）
**Repo:** python-pillow/Pillow | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
The following vulnerabilities are reported against libtiff in Pillow, would you please confirm if Pillow is affected by them?
CVE-2023-30774
OS: Ubuntu 22.04 LTS
Python: 3.9.16
Pillow: 9.3.0
```

### Drafted eval_question
```
The following vulnerabilities are reported against libtiff in Pillow, would you please confirm if Pillow is affected by them? CVE-2023-30774 OS: Ubuntu 22.04 LTS Python: 3.9.16 Pillow: 9.3.0
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2023-30774'] | NEEDS REVIEW | Reporter cited: ['CVE-2023-30774', '9.3.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/7137
**Title:** LibTIFF vulnerabilities (CVE-2023-0795, CVE-2023-0796, CVE-2023-0797, CVE-2023-0798, CVE-2023-0799, CVE-2023-0800, CVE-2023-0801, CVE-2023-0802, CVE-2023-0803, CVE-2023-0804)
**Repo:** python-pillow/Pillow | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
The following vulnerabilities are reported against libtiff in Pillow, would you please confirm if Pillow is affected by them?

1. [CVE-2023-0795](https://nvd.nist.gov/vuln/detail/CVE-2023-0795)
1. [CVE-2023-0796](https://nvd.nist.gov/vuln/detail/CVE-2023-0796)
1. [CVE-2023-0797](https://nvd.nist.gov/vuln/detail/CVE-2023-0797)
1. [CVE-2023-0798](https://nvd.nist.gov/vuln/detail/CVE-2023-0798)
1. [CVE-2023-0799](https://nvd.nist.gov/vuln/detail/CVE-2023-0799)
1. [CVE-2023-0800](https://nvd.nist.gov/vuln/detail/CVE-2023-0800)
1. [CVE-2023-0801](https://nvd.nist.gov/vuln/detail/CVE-2023-0801)
1. [CVE-2023-0802](https://nvd.nist.gov/vuln/detail/CVE-2023-0802)
1. [CVE-2023-0803](https://nvd.nist.gov/vuln/detail/CVE-2023-0803)
1. [CVE-2023-0804](https://nvd.nist.gov/vuln/detail/CVE-2023-0804)

OS: Ubuntu 22.04 LTS
Python: 3.9.16
Pillow: 9.5.0
```

### Drafted eval_question
```
The following vulnerabilities are reported against libtiff in Pillow, would you please confirm if Pillow is affected by them? 1. CVE-2023-0795 2. CVE-2023-0796 3. CVE-2023-0797 4. CVE-2023-0798 5. CVE-2023-0799 6. CVE-2023-0800 7. CVE-2023-0801 8. CVE-2023-0802 9. CVE-2023-0803 10. CVE-2023-0804 OS: Ubuntu 22.04 LTS Python: 3.9.16 Pillow: 9.5.0
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2023-0795', 'cve_ids:CVE-2023-0796', 'cve_ids:CVE-2023-0797', 'cve_ids:CVE-2023-0798', 'cve_ids:CVE-2023-0799', 'cve_ids:CVE-2023-0800', 'cve_ids:CVE-2023-0801', 'cve_ids:CVE-2023-0802', 'cve_ids:CVE-2023-0803', 'cve_ids:CVE-2023-0804'] | NEEDS REVIEW | Reporter cited: ['CVE-2023-0795', 'CVE-2023-0796', 'CVE-2023-0797', 'CVE-2023-0798', 'CVE-2023-0799', 'CVE-2023-0800', 'CVE-2023-0801', 'CVE-2023-0802', 'CVE-2023-0803', 'CVE-2023-0804']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/7031
**Title:** Libtiff vulnerabilities (CVE-2022-4645)
**Repo:** python-pillow/Pillow | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
There are some vulnerabilities of libtiff within Pillow.
Please confirm whether you are affected by them.



https://nvd.nist.gov/vuln/detail/CVE-2022-4645

What are your OS, Python and Pillow versions?
OS: Linux
Python: 3.9
Pillow: 9.3.0
```

### Drafted eval_question
```
There are some vulnerabilities of libtiff within Pillow. Please confirm whether you are affected by them. What are your OS, Python and Pillow versions? OS: Linux Python: 3.9 Pillow: 9.3.0
```

**Flags:** Reporter cited: ['CVE-2022-4645']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/6955
**Title:** Libtiff vulnerabilities  (CVE-2022-2519, CVE-2022-2520, CVE-2022-48281)
**Repo:** python-pillow/Pillow | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
Excuse me, are the remaining three vulnerabilities affected?
CVE-2022-2519, CVE-2022-2520, CVE-2022-48281
```

### Drafted eval_question
```
Are the following vulnerabilities affecting Pillow version 9.3.0 on Linux with Python 3.9: CVE-2022-2519, CVE-2022-2520, and CVE-2022-48281? Previously, version 9.2.0 was confirmed unaffected, but I am unsure about the current version.
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2022-2519', 'cve_ids:CVE-2022-2520', 'cve_ids:CVE-2022-48281'] | NEEDS REVIEW | Reporter cited: ['CVE-2022-2519', 'CVE-2022-2520', 'CVE-2022-48281']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/6687
**Title:** Pip audit reporting security vulnerability OSV-2022-715
**Repo:** python-pillow/Pillow | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
We run pip-audit and just this week started reporting a security vulnerability with 9.2.0, we are running python 3.10.8.

https://osv.dev/vulnerability/OSV-2022-715

When you follow the References link in the issue, it says something about being fixed.

https://bugs.chromium.org/p/oss-fuzz/issues/detail?id=50217

But yet `pip-audit` is still flagging.

Should we be treating this as a false flag?  Problem is with `pip-audit` and it's source of vulnerabilities?  Or is this something that needs to be investigated?
```

### Drafted eval_question
```
We run pip-audit and just this week it started reporting a security vulnerability with Pillow version 9.2.0, while we are using Python 3.10.8. The vulnerability is referenced as OSV-2022-715. When following the References link in the issue, it indicates that the issue has been fixed. However, pip-audit is still flagging it. Should we be treating this as a false flag? Is the problem with pip-audit and its source of vulnerabilities, or is this something that needs to be investigated?
```

**Flags:** LEAK FLAGS: ['osv_ids:OSV-2022-715'] | NEEDS REVIEW | Reporter cited: ['OSV-2022-715']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/6665
**Title:** Libtiff vulnerability (CVE-2022-34526）
**Repo:** python-pillow/Pillow | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
There are some vulnerabilities of libtiff within Pillow.
Please confirm whether you are affected by them.

CVE-2022-34526

What are your OS, Python and Pillow versions?
OS: Linux
Python: 3.9
Pillow: 9.2.0
```

### Drafted eval_question
```
There are some vulnerabilities of libtiff within Pillow. Please confirm whether you are affected by them. CVE-2022-34526. What are your OS, Python and Pillow versions? OS: Linux Python: 3.9 Pillow: 9.2.0
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2022-34526'] | NEEDS REVIEW | Reporter cited: ['CVE-2022-34526']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## python-pillow/Pillow/issue/6407
**Title:** namecheap shared hosting can't install newer than Pillow==8.3.2
**Repo:** python-pillow/Pillow | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Hi

On namecheap  i get an error when install pillow, there is [a question on stackoverflow but without anwser,](https://stackoverflow.com/questions/71275309/how-to-install-pillow-on-namecheap-server#comment126017694_71275309)





* OS: 
```
 $ cat /proc/version

Linux version 2.6.32-954.3.5.lve1.4.81.el6.x86_64 (mockbuild@buildfarm02.cloudlinux.com) 
(gcc version 4.4.7 20120313 (Red Hat 4.4.7-23) (GCC) ) #1 SMP Mon Feb 1 12:39:21 EST 2021

 ```
( gcc  4 is that the main problem? )

* Python: v3.9.12
* Pillow: pillow==9.1.1


* The latest version that i can install pillow==8.3.2, 
### Is it save to use an old versions like pillow==8.3.2 on productions? ( i am using Django 4.0.4 )

```
pip install pillow==8.3.2
Collecting pillow==8.3.2
  Using cached Pillow-8.3.2-cp39-cp39-manylinux_2_5_x86_64.manylinux1_x86_64.whl (3.0 MB)
Installing collected packages: pillow
  Attempting uninstall: pillow
    Found existing installation: Pillow 8.3.0
    Uninstalling ...
```

### Drafted eval_question
```
(ERROR — see eval_questions.jsonl)
```

**Flags:** NEEDS REVIEW | ERROR: LLM returned non-JSON: {
  "eval_question": "I am using Namecheap shared hosting with Linux version 2.6.32-954.3.5.lve1.4.81.el6.x86_64 and Python v3.9.12. I am trying to install Pillow version 9.1.1, but I encounter an error during the build process. The latest version I can successfully install is Pillow 8.3.2. Here is 

**Approved:** [ ] (set `approved:true` in JSONL)

---

## rails/rails/issue/54343
**Title:** PoolConfig caches the connection_class, which breaks if it is reloaded
**Repo:** rails/rails | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
Yeah, that is a real problem. This can affect many apps that have no choice to not reload the connection classes. I looked why we need to hold the class (we generally avoid that exactly because of reload), and it is since https://github.com/rails/rails/commit/05821c6c649079a63e3af0d2b3b4fa3ae2056801.

@eileencodes any idea on how to fix this problem?
```

### Drafted eval_question
```
I've been debugging an issue with Solid Cache, which seems to be caused by reloading the connection class in Rails. The connection class is stored in `ActiveRecord::ConnectionAdapters::PoolConfig`, and if it is reloaded, it no longer matches the stored value. This causes checks to fail, leading to issues like the one observed in Solid Cache. Here's a reproduction in a development console using Solid Cache:

```ruby
>> ActiveRecord::Base.connected_to(role: ActiveRecord.reading_role, prevent_writes: true) do 
  SolidCache::Record.connected_to(shard: :cache, role: :writing, prevent_writes: false) do
     puts SolidCache::Record.connection.preventing_writes?
  end
end
false
=> nil
>> reload!
Reloading...
>> ActiveRecord::Base.connected_to(role: ActiveRecord.reading_role, prevent_writes: true) do 
  SolidCache::Record.connected_to(shard: :cache, role: :writing, prevent_writes: false) do
     puts SolidCache::Record.connection.preventing_writes?
  end
end
true
=> nil
```

I can prevent `SolidCache::Record` from being reloaded to fix this for Solid Cache, but this could still be an issue for any application-specific connection classes. Is there a way to address this problem in Rails?
```

**Flags:** Reporter cited: ['31f8a6b6cce5e38f1f8a9532d441c4d19ca8fb08', '05821c6c649079a63e3af0d2b3b4fa3ae2056801']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## rails/rails/issue/56736
**Title:** Accessing the key generator in an initializer silently changes the hash digest class for the entire application
**Repo:** rails/rails | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Steps to reproduce

Create a new Rails application and add `config/initializers/repro.rb` with:

```ruby
Rails.application.key_generator
```

And run:

```sh
rails runner "p Rails.application.key_generator.instance_variable_get(:@key_generator).instance_variable_get(:@hash_digest_class)"
```

### Expected behavior

`OpenSSL::Digest::SHA256`, which is the output without the initializer.

### Actual behavior

`OpenSSL::Digest::SHA1`

### System configuration

**Rails version**: 8.1.2

**Ruby version**: 3.4.8

### Additional notes

turbo-rails was [affected by this](https://github.com/hotwired/turbo-rails/blob/v8.0.21/UPGRADING.md#key-digest-changes-in-111) and made a change to initialization to workaround it.

A few ideas to address this would be:

- apply `config.active_support.key_generator_hash_digest_class` earlier in initialization
- warn or raise if `Rails.application.key_generator` is already cached when applying `config.active_support.key_generator_hash_digest_class`
- includ...
```

### Drafted eval_question
```
In a Rails 8.1.2 application running on Ruby 3.4.8, accessing the key generator in an initializer changes the hash digest class from `OpenSSL::Digest::SHA256` to `OpenSSL::Digest::SHA1`. Is this behavior a genuine security vulnerability in Rails? How can this issue be addressed to ensure the expected hash digest class is used throughout the application? Here is a code snippet to reproduce the issue:

```ruby
Rails.application.key_generator
```

And the command to observe the behavior:

```sh
rails runner "p Rails.application.key_generator.instance_variable_get(:@key_generator).instance_variable_get(:@hash_digest_class)"
```

Additionally, turbo-rails was affected by this and made a change to initialization to workaround it. What are the recommended solutions to prevent this issue?
```

**Flags:** Reporter cited: ['8.1.2', '3.4.8', 'https://github.com/hotwired/turbo-rails/blob/v8.0.21/UPGRADING.md#key-digest-changes-in-111']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## rails/rails/issue/56158
**Title:** Deadlocked transactions are still seen as "usable" for MySQL (trilogy / mysql2)
**Repo:** rails/rails | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Steps to reproduce

<!-- (Guidelines for creating a bug report are [available
here](https://edgeguides.rubyonrails.org/contributing_to_ruby_on_rails.html#creating-a-bug-report)) -->

<!-- Paste your executable test case created from one of the scripts found [here](https://edgeguides.rubyonrails.org/contributing_to_ruby_on_rails.html#create-an-executable-test-case) below: -->

[Full reproduction script gist](https://gist.github.com/ipvalverde/2d2f6b91d593e09b89a86a7c61a3ca5b). Important bit:

```ruby
Account.transaction do
  Account.create!(name: "Account in top-level transaction", balance: 50)

  begin
    puts "1) Is transaction open? #{Account.connection.transaction_open?}"

    # consider the logic in here will raise a deadlock:
    Account.lock.find(1).update!(balance: 10)
    Account.lock.find(2).update!(balance: 20)

  rescue ActiveRecord::Deadlocked => e
    puts "2) Is transaction open? #{Account.connection.transaction_open?}"

    # Everything up to this point is DISCARDED...
```

### Drafted eval_question
```
In Rails 8.1.1 with Ruby 3.4.4, when using MySQL (trilogy/mysql2), transactions that encounter a deadlock are still considered 'usable', allowing subsequent database write operations to proceed without an active transaction. This behavior differs from PostgreSQL, which raises an error when attempting further operations after a deadlock. Is this behavior a genuine issue with MySQL in Rails, and should database operations fail if there's no transaction open after a deadlock? Here is a reproduction script demonstrating the issue:

```ruby
Account.transaction do
  Account.create!(name: "Account in top-level transaction", balance: 50)

  begin
    puts "1) Is transaction open? #{Account.connection.transaction_open?}"

    # consider the logic in here will raise a deadlock:
    Account.lock.find(1).update!(balance: 10)
    Account.lock.find(2).update!(balance: 20)

  rescue ActiveRecord::Deadlocked => e
    puts "2) Is transaction open? #{Account.connection.transaction_open?}"

    # Everything up to this point is DISCARDED from the Database perspective.
    # No account being created, no accounts being updated.
    
  end

  # This will write directly to the database - no valid transactions in here.
  Account.create!(name: "Last account in top-level transaction", balance: 999)

  # this will be a no-op since there's no transaction open
  raise ActiveRecord::Rollback
end
```
```

**Flags:** Reporter cited: ['8.1.1', '3.4.4']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## rails/rails/issue/55528
**Title:** Breaking functionality after patch
**Repo:** rails/rails | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Steps to reproduce

You will also need a `config/storage` with a basic `test` service set up:

```yaml
test:
  service: Disk
  root: <%= Rails.root.join("storage") %>
```

And also a `spec/fixtures/sample.tiff` with any TIFF file:
[sample.tiff](https://github.com/user-attachments/files/21925383/sample.tiff)

```ruby
# frozen_string_literal: true

require "bundler/inline"

gemfile(true) do
  source "https://rubygems.org"

  gem "rails", "8.0.2.1" # ---> Tests passes with Rails 8.0.2

  gem "sqlite3"
  gem "image_processing"
end

require "active_record/railtie"
require "minitest/autorun"
require "active_storage/engine"

# This connection will do for database-independent bug reports.
ENV["DATABASE_URL"] = "sqlite3::memory:"

class TestApp < Rails::Application
  config.load_defaults Rails::VERSION::STRING.to_f
  config.eager_load = false
  config.logger = Logger.new($stdout)
  config.secret_key_base = "secret_key_base"

  config.active_record.encryption.primary_key = "primary_key"
  co...
```

### Drafted eval_question
```
In Rails 8.0.2.1, the TIFF to PDF conversion is failing because the `loader` attribute is no longer supported. The following code demonstrates the issue:

```ruby
# frozen_string_literal: true

require "bundler/inline"

gemfile(true) do
  source "https://rubygems.org"

  gem "rails", "8.0.2.1" # ---> Tests passes with Rails 8.0.2

  gem "sqlite3"
  gem "image_processing"
end

require "active_record/railtie"
require "minitest/autorun"
require "active_storage/engine"

# This connection will do for database-independent bug reports.
ENV["DATABASE_URL"] = "sqlite3::memory:"

class TestApp < Rails::Application
  config.load_defaults Rails::VERSION::STRING.to_f
  config.eager_load = false
  config.logger = Logger.new($stdout)
  config.secret_key_base = "secret_key_base"

  config.active_record.encryption.primary_key = "primary_key"
  config.active_record.encryption.deterministic_key = "deterministic_key"
  config.active_record.encryption.key_derivation_salt = "key_derivation_salt"

  config.active_storage.service = :test
  config.active_storage.variant_processor = :mini_magick
end
Rails.application.initialize!

ActiveRecord::Schema.define do
  create_table :posts, force: true do |t|
  end

  create_table :active_storage_attachments do |t|
    t.string     :name, null: false
    t.references :record, null: false, polymorphic: true, index: false
    t.references :blob, null: false
    t.datetime   :created_at, null: false
    t.index      [:record_type, :record_id, :name, :blob_id], name: "index_active_storage_attachments_uniqueness", unique: true
  end

  create_table :active_storage_blobs do |t|
    t.string   :key,        null: false
    t.string   :filename,   null: false
    t.string   :content_type
    t.text     :service_name, null: false
    t.bigint   :byte_size, null: false
    t.string   :checksum, null: false
    t.datetime :created_at, null: false
  end

  create_table :active_storage_variant_records do |t|
    t.belongs_to :blob, null: false, index: false
    t.string :variation_digest, null: false
    t.index %i[ blob_id variation_digest ], name: "index_active_storage_variant_records_uniqueness", unique: true
    t.string :variation_key
  end
end

class Post < ActiveRecord::Base
  has_one_attached :file do |attachable|
    # [loader, saver, apply] were removed in Rails 8.0.2.1
    attachable.variant :tiff_to_pdf, convert: :pdf, format: :pdf, loader: { page: nil }
  end
end

class BugTest < ActiveSupport::TestCase
  def test_tiff_to_pdf_variant
    post = Post.create!
    post.file.attach(io: File.open(Rails.root.join('spec', 'fixtures', 'sample.tiff')), filename: 'sample.tiff', content_type: 'image/tiff')
    post.file.variant(:tiff_to_pdf).processed

    assert_equal 'application/pdf', post.file.variant(:tiff_to_pdf).image.blob.content_type
    assert_equal 'sample.pdf', post.file.variant(:tiff_to_pdf).image.blob.filename.to_s
  end
end
```

Is this behavior a genuine security vulnerability in Rails 8.0.2.1, or is there a workaround to restore the functionality?
```

**Flags:** Reporter cited: ['8.0.2.1']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## rails/rails/issue/55245
**Title:** Handle links and other safe content inside translations
**Repo:** rails/rails | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
Currently, if I want to put a link into a translation, I have to do
```erb
<%= t(".text", insert: link_to(t(".insert"), root_path)).html_safe %>
```
or
```erb
<%= t(".text_html", insert: link_to(t(".insert"), root_path)) %>
```

However, the `text_html` translation should not have to know whether the `insert` contains html or not.
~Also, the `insert` translation cannot have unescaped html content, because it is used as content inside another `_html` translation.~

The rails i18n guide does not mention how to do this nicely.

The best would be if rails-i18n could handle it automatically by being aware of SafeBuffer.

```yml
text: some <> text with an %{insert}
text_html: some &lt;&gt; text with an %{insert}
insert: a link, properly escaping <>
```

```erb
<%= t(".text", insert: link_to(t(".insert"), root_path)) %>
```

Rails-i18n should handle safe joining the above example.

`link_to` returns a `html_safe` string, so this should output 
```html
some &lt;&gt; text with an <a href="/">a ...
```

### Drafted eval_question
```
In Rails, when inserting links or other HTML content into translations, the current approach requires using either `html_safe` or a separate `_html` translation key. This is cumbersome and requires the translation to be aware of whether its variables contain HTML. Is there a way for Rails to automatically handle safe joining of HTML content in translations by leveraging SafeBuffer, so that translations do not need to know if their variables contain HTML? For example, given the YAML translations:

```yml
text: some <> text with an %{insert}
text_html: some &lt;&gt; text with an %{insert}
insert: a link, properly escaping <>
```

And the ERB code:

```erb
<%= t(".text", insert: link_to(t(".insert"), root_path)) %>
```

Rails should output:

```html
some &lt;&gt; text with an <a href="/">a link, properly escaping &lt;&gt;</a>
```

How can this be implemented in Rails to handle such cases automatically?
```

**Flags:** Reporter cited: ['36601bbb02bc3570f5609db2127c77afca575d6c', '3235827585d87661942c91bc81f64f56d710f0b2']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## rails/rails/issue/55219
**Title:** Authentication generator missing rate limiting on PasswordsController despite ActionMailer being available
**Repo:** rails/rails | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
# Authentication generator missing rate limiting on PasswordsController

## Description

The Rails 8 authentication generator is missing rate limiting on the `PasswordsController` despite ActionMailer being available. This leaves the password reset endpoint vulnerable to abuse.

## Steps to reproduce

```bash
# Create a new Rails application
rails new test_app
cd test_app

# Verify ActionMailer is available
rails runner "puts defined?(ActionMailer::Railtie)"
# Output: "constant"

# Generate authentication
rails generate authentication

# Check the generated PasswordsController
cat app/controllers/passwords_controller.rb
```

## Expected behavior

The generated `PasswordsController` should include rate limiting on the `create` action when ActionMailer is available:

```ruby
rate_limit to: 10, within: 3.minutes, only: :create, with: -> { redirect_to new_password_path, alert: "Try again later." }
```

This protection is essential to prevent abuse of the password reset email functionality....
```

### Drafted eval_question
```
In Rails 8, the authentication generator is supposed to include rate limiting in the PasswordsController when ActionMailer is available, to prevent abuse of the password reset functionality. However, the generated PasswordsController is missing this rate limiting, leaving the endpoint vulnerable to abuse. The ERB template for the generator seems to have a conditional that should add rate limiting if ActionMailer is defined, but it is not working as expected. Why is the rate limiting not being included, and how can this issue be resolved?
```

**Flags:** Reporter cited: ['8.0.0', '3.2.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## rails/rails/issue/54926
**Title:** Signed cookies use SHA-1 by default
**Repo:** rails/rails | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Steps to reproduce

<!-- (Guidelines for creating a bug report are [available
here](https://edgeguides.rubyonrails.org/contributing_to_ruby_on_rails.html#creating-a-bug-report)) -->

In a new rails app, create a signed cookie with `cookies.signed[:foo] = 'bar'`.

### Expected behavior

Signed cookies use a secure-by-default signing method such as SHA-256.

<!-- Tell us what should happen -->

### Actual behavior

In the controller if you then call `cookies.send :signed_cookie_digest`, you get "SHA1".


https://guides.rubyonrails.org/configuring.html#config-action-dispatch-signed-cookie-digest does document that the default for signed_cookie_digest is "SHA1", though the upgrade guide for Rails 7.0 implied this was changing to SHA-256:
https://guides.rubyonrails.org/upgrading_ruby_on_rails.html#digest-class-for-activesupport-digest-changing-to-sha256

and the active support digest class did in fact change to SHA-256:
https://guides.rubyonrails.org/configuring.html#config-active-suppo...
```

### Drafted eval_question
```
In a new Rails 8.0.1 application, when creating a signed cookie using `cookies.signed[:foo] = 'bar'`, the expected behavior is for the signed cookies to use a secure-by-default signing method such as SHA-256. However, when calling `cookies.send :signed_cookie_digest` in the controller, it returns 'SHA1'. The Rails documentation indicates that the default for `signed_cookie_digest` is 'SHA1', but the Rails 7.0 upgrade guide implied a change to SHA-256, and the Active Support digest class did change to SHA-256. Why does the cookie digest class still use SHA-1, and is this a security concern?
```

**Flags:** Reporter cited: ['7.0', '8.0.1']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## stripe/stripe-node/issue/2534
**Title:** Upgrade transitive dependency qs to >= 6.14.1 to address CVE-2025-15284
**Repo:** stripe/stripe-node | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Is your feature request related to a problem? Please describe.

**Issue Description**

Hello Stripe team 👋,

We are currently using the Stripe Node SDK and noticed that it pulls in a vulnerable version of the qs package as a transitive dependency.

The qs versions < 6.14.1 are affected by CVE-2025-15284 / GHSA-6rw7-vpxm-498p, where the arrayLimit option can be bypassed using bracket notation (a[]=x), allowing unbounded array creation and leading to potential Denial of Service via memory exhaustion.

**Affected Dependency Chain**
stripe → qs@^6.11.0

This version range resolves to a vulnerable qs release.

**Impact**

Even when applications configure arrayLimit in qs.parse(), the limit is ignored for bracket notation (a[]=value), which makes it possible for an attacker to submit a single crafted request that consumes excessive memory.

This issue is particularly impactful for applications parsing user-controlled query strings or request bodies.

### Describe the solution you'd like
...
```

### Drafted eval_question
```
We are using the Stripe Node SDK, which includes a vulnerable version of the qs package as a transitive dependency. The versions of qs below 6.14.1 are affected by CVE-2025-15284 / GHSA-6rw7-vpxm-498p, where the arrayLimit option can be bypassed using bracket notation, potentially leading to Denial of Service via memory exhaustion. The affected dependency chain is stripe → qs@^6.11.0. Is this a genuine security vulnerability in the Stripe Node SDK, and should we upgrade the qs dependency to version 6.14.1 or later to mitigate this issue?
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2025-15284', 'ghsa_ids:GHSA-6rw7-vpxm-498p'] | NEEDS REVIEW | Reporter cited: ['CVE-2025-15284', 'GHSA-6rw7-vpxm-498p', 'qs@^6.11.0', 'qs >= 6.14.1']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## stripe/stripe-node/issue/2530
**Title:** Upgrade `qs`
**Repo:** stripe/stripe-node | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Is your feature request related to a problem? Please describe.

`qs` is v6.11.0

### Describe the solution you'd like

qs  <6.14.1
Severity: high
qs's arrayLimit bypass in its bracket notation allows DoS via memory exhaustion - https://github.com/advisories/GHSA-6rw7-vpxm-498p

### Describe alternatives you've considered

_No response_

### Additional context

_No response_
```

### Drafted eval_question
```
Is the version of the `qs` library (v6.11.0) used in the stripe/stripe-node repository vulnerable to a high severity denial of service (DoS) attack due to the arrayLimit bypass in its bracket notation, as described in the advisory https://github.com/advisories/GHSA-6rw7-vpxm-498p? Should it be upgraded to a version >=6.14.1 to mitigate this issue?
```

**Flags:** LEAK FLAGS: ['ghsa_ids:GHSA-6rw7-vpxm-498p', 'advisory_urls:https://github.com/advisories/GHSA-6rw7-vpxm-498p'] | NEEDS REVIEW | Reporter cited: ['GHSA-6rw7-vpxm-498p', '6.11.0', '6.14.1']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## stripe/stripe-node/issue/1784
**Title:** Wrong type definition for create external account
**Repo:** stripe/stripe-node | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Describe the bug

`external_account` property type inside `ExternalAccountCreateParams` is set to be `string` but it needs to be `string | <object with type of new external account>` just like how it is supported already in `AccountCreateParams` under `external_account`. 

Currently it is not possible to simply create an external account with object type and attach it to the account by id.


https://github.com/stripe/stripe-node/blob/e7800b3d5e689e23fece91f89f727af24ddf32a4/types/AccountsResource.d.ts#L2482

### To Reproduce

1. Create an account
2. Create an external account with details and attach to above account

### Expected behavior

1. Create account
2. Create an external account with details and attach to above account

### Code snippets

```JavaScript
const input: Stripe.ExternalAccountCreateParams = {
    default_for_currency: true,
    external_account: {
      object: "bank_account",
      account_holder_name: params.holderName,
      account_...
```

### Drafted eval_question
```
Is the type definition for the `external_account` property in `ExternalAccountCreateParams` incorrect in stripe-node version ^11.1.0? It is currently set to `string`, but it should support `string | <object with type of new external account>`, similar to `AccountCreateParams`. This issue prevents creating an external account with object type and attaching it to an account by ID. Here is a code snippet demonstrating the problem:

```JavaScript
const input: Stripe.ExternalAccountCreateParams = {
    default_for_currency: true,
    external_account: {
      object: "bank_account",
      account_holder_name: params.holderName,
      account_number: params.ibanNumber,
      account_holder_type: "individual",
      country: "DK",
      currency: "DKK",
    }
  };
  const externalAccount = await stripe.accounts.createExternalAccount(
    params.id,
    input
  );
```

Is this a genuine issue with the type definition, and if so, how can it be resolved?
```

**Flags:** Reporter cited: ['^11.1.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## stripe/stripe-node/issue/877
**Title:** Feature request: idempotency for Payment Intents
**Repo:** stripe/stripe-node | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
I can not find in API that Payment intents do support idempotency keys (like charges). This causes potential double-charging situation for me when using off session payments. I am using this code:

```
const paymentIntent = await stripe.paymentIntents.create({
    amount: 1099,
    currency: 'usd',
    customer: '{{CUSTOMER_ID}}',
    payment_method: '{{PAYMENT_METHOD_ID}}',
    off_session: true,
    confirm: true,
  });
```

In case there is a bug in my code and this code gets executed twice - the client would be charged twice. However if I could add some idempotency value that I could pass to intent creation (lets say it could be order id). That would mean that it would be impossible to create two off_session aut-confirmable payment intents for the same order.
```

### Drafted eval_question
```
Does the Stripe API support idempotency keys for Payment Intents similar to how it does for charges? I am concerned about potential double-charging when using off-session payments with the following code: 

```
const paymentIntent = await stripe.paymentIntents.create({
    amount: 1099,
    currency: 'usd',
    customer: '{{CUSTOMER_ID}}',
    payment_method: '{{PAYMENT_METHOD_ID}}',
    off_session: true,
    confirm: true,
  });
```

If this code is executed twice due to a bug, the client could be charged twice. I would like to know if there is a way to add an idempotency value, such as an order ID, to prevent this issue.
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## stripe/stripe-node/issue/844
**Title:** Inconsistent description and TS type in `external_account`
**Repo:** stripe/stripe-node | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
For the `AccountUpdateParams`:

Using the old `@types/stripe` it was possible to define `external_account` as an object, which I think it is the intented behavior, based on the current description of the property, but the only accepted type is `string`.

```ts
/**
 * A card or bank account to attach to the account. You can provide either a token, like the ones returned by [Stripe.js](https://stripe.com/docs/stripe.js), or a dictionary, as documented in the `external_account` parameter for [bank account](https://stripe.com/docs/api#account_create_bank_account) creation.
 *
 * By default, providing an external account sets it as the new default external account for its currency, and deletes the old default if one exists. To add additional external accounts without replacing the existing default for the currency, use the bank account or card creation API.
 */
external_account?: string;
```

Is this a bug or a new behavior?


```

### Drafted eval_question
```
In the `stripe-node` library, specifically for `AccountUpdateParams`, the `external_account` property is described as allowing either a token or a dictionary, similar to the behavior in the old `@types/stripe`. However, the current TypeScript type only accepts a `string`. Is this inconsistency a bug or an intended new behavior?
```

**Approved:** [ ] (set `approved:true` in JSONL)

---

## urllib3/urllib3/issue/3734
**Title:** Brotli DecodeError with chunked transfer encoding: "can_accept_more_data() is False"
**Repo:** urllib3/urllib3 | **Source:** issue_body | **Model:** gpt-4o

### Raw question body
```
### Subject

When receiving a large brotli-compressed response with chunked transfer encoding, urllib3 2.6.x raises a `DecodeError` with the message:

```
brotli: decoder process called with data when 'can_accept_more_data()' is False
```

This appears to be a regression introduced in urllib3 2.6.0, likely related to the security changes for handling compressed content (GHSA-2xpw-w6gg-jr37). The issue occurs specifically when:
1. The response uses `Content-Encoding: br` (brotli)
2. The response uses `Transfer-Encoding: chunked`
3. The compressed data is moderately large (~500KB+ compressed)
4. Data arrives in small TCP segments

The issue does **not** occur with urllib3 2.5.0.

### Environment

```
OS: Linux 6.x (Debian Bookworm in Docker)
Python: 3.12.12
OpenSSL: OpenSSL 3.0.x
urllib3: 2.6.1
brotli: 1.2.0
requests: 2.31.0
```

Works correctly with:
```
urllib3: 2.5.0
brotli: 1.1.0
```

### Steps to Reproduce

Minimal reproduction script:

```python
#!/usr/bin/env python3
"""Minimal re...
```

### Drafted eval_question
```
When using urllib3 version 2.6.x with brotli 1.2.0, I encounter a `DecodeError` when receiving a large brotli-compressed response with chunked transfer encoding. The error message is: 'brotli: decoder process called with data when can_accept_more_data() is False'. This issue does not occur with urllib3 2.5.0 and brotli 1.1.0. Is this a regression in urllib3 2.6.0 related to the security changes for handling compressed content (GHSA-2xpw-w6gg-jr37), or is it more related to the brotli update? How can I resolve this issue? Here is a minimal reproduction script:

```python
#!/usr/bin/env python3
"""Minimal reproduction: brotli decode bug with urllib3 2.6.x + brotli 1.2.0"""

import hashlib
import socket
import threading

import brotli
import requests


def main() -> int:
    from importlib.metadata import version

    print(f"urllib3: {version('urllib3')}, brotli: {version('brotli')}")

    # Generate ~15MB data with moderate compressibility (~27x ratio)
    data = b"".join(
        f"{hashlib.sha256(str(i).encode()).hexdigest()}{'a' * 900}{i:06d}\n".encode()
        for i in range(15000)
    )
    compressed = brotli.compress(data)
    print(f"Data: {len(data):,} -> {len(compressed):,} bytes ({len(data) // len(compressed)}x)")

    # Build chunked HTTP response
    resp = b"HTTP/1.1 200 OK\r\nContent-Encoding: br\r\nTransfer-Encoding: chunked\r\n\r\n"
    for i in range(0, len(compressed), 32768):
        chunk = compressed[i : i + 32768]
        resp += f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n"
    resp += b"0\r\n\r\n"

    # Start mock server
    ready = threading.Event()

    def serve(port: int) -> None:
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", port))
        s.listen(1)
        ready.set()
        c, _ = s.accept()
        c.recv(4096)
        for i in range(0, len(resp), 128):  # Small chunks trigger bug
            c.send(resp[i : i + 128])
        c.close()
        s.close()

    threading.Thread(target=serve, args=(18765,), daemon=True).start()
    ready.wait()

    try:
        r = requests.get("http://127.0.0.1:18765/", timeout=60)
        print(f"SUCCESS: {len(r.content):,} bytes")
        return 0
    except requests.exceptions.ContentDecodingError as e:
        print(f"FAILED: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
```
```

**Flags:** LEAK FLAGS: ['ghsa_ids:GHSA-2xpw-w6gg-jr37'] | NEEDS REVIEW | Reporter cited: ['GHSA-2xpw-w6gg-jr37', '2.6.0', '2.5.0']

**Approved:** [ ] (set `approved:true` in JSONL)

---

## urllib3/urllib3/issue/3640
**Title:** CVE-2025-50182 affected versions
**Repo:** urllib3/urllib3 | **Source:** thread_comment | **Model:** gpt-4o

### Raw question body
```
I see.. so if I understand it correct, basically the vulnerable part in 2.2.0 is out of the reach of the project, and virtually unpatchable from within urllib3?
```

### Drafted eval_question
```
I would like to ask for some clarification regarding CVE-2025-50182, specifically the versions of urllib3 that it affects. The CVE description marks 2.2.0 as the first vulnerable version. However, based on the fix commit and the description, it seems like the vulnerability is present when using the js.fetch() function, which appears to have been introduced in version 2.3.0. Was the vulnerability introduced in version 2.3.0, or is version 2.2.0 vulnerable in another way that I might have missed?
```

**Flags:** LEAK FLAGS: ['cve_ids:CVE-2025-50182'] | NEEDS REVIEW | Reporter cited: ['CVE-2025-50182', '2.2.0', '2.3.0', 'https://github.com/urllib3/urllib3/commit/7eb4a2aafe49a279c29b6d1f0ed0f42e9736194f', 'https://github.com/urllib3/urllib3/commit/8b2474d32b57f096a815ab52f9b54a843d68c140']

**Approved:** [ ] (set `approved:true` in JSONL)

---
