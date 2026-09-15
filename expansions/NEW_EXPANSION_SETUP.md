# New Expansion Setup Checklist

Before a new expansion is reachable on its custom domain, three pieces of AWS/Namecheap infrastructure need to be told about the new subdomain.

## 1. Update the CloudFront function

The viewer-request function in CloudFront currently maps known subdomains (e.g. `monuments.cacotopos.com`) to the matching S3 prefix. Add a branch for the new subdomain:

```javascript
if (request.headers['host'].value === '{subdomain}.cacotopos.com') {
    request.uri = '/{subdomain}' + request.uri;
}
```

Or, if the function is written the other way around, append `{ subdomain: '{subdomain}' }` to the routing table.

## 2. Add the subdomain to the ACM certificate

Open **AWS Certificate Manager** and either:

- Request a new certificate for `*.cacotopos.com` (if one is not already in use), or
- Add a new name `{subdomain}.cacotopos.com` to the existing certificate and validate it via DNS/email.

## 3. Add the DNS record in Namecheap

Open the Namecheap **Advanced DNS** page for `cacotopos.com` and add a record for the new subdomain:

| Type | Host | Value | TTL |
|------|------|-------|-----|
| CNAME Record | `{subdomain}` | `<CloudFront distribution hostname>` | Automatic |

The CloudFront distribution hostname looks like `d39rtkg7d9lwsg.cloudfront.net`.

## 4. (Optional) CloudFront alternate domain

If the distribution does not already use a wildcard alternate domain (`*.cacotopos.com`), add `{subdomain}.cacotopos.com` to the distribution's **Alternate domain names (CNAMEs)** list and attach the ACM certificate.

---

Once all three are in place, the expansion will be available at:

```
https://{subdomain}.cacotopos.com
```

Until then, the S3 static-website URL (returned by the deploy response) still works for testing.
