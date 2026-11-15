# cTrader native OCO recheck

Research checked 2026-11-15 for the live strategy capability decision. No broker
session, order, or account mutation was performed.

## Conclusion

The published Open API protocol does not expose a request or parameter for
creating an arbitrary one-cancels-the-other (OCO) relationship between two pending
entry orders. This conclusion is about the available public contract; it does not
prove that cTrader servers have no internal OCO functionality. Native OCO should
not be promised for this integration without a concrete supported request from
Spotware.

## Open API evidence

The official protocol was checked at commit
`a9676f27f40b60569fb8a510aeadedba901b74e9`. Its request definitions, including new,
amend, and cancel order requests, provide no OCO/group/contingency creation
operation or relationship field. `positionId` addresses an existing position;
`label` and `clientOrderId` are identification metadata, not cancellation rules.
The order-type enum lists market, limit, stop, stop-loss/take-profit, market-range,
and stop-limit; none establishes an arbitrary paired-entry cancellation rule.
Sources: [request schema](https://github.com/spotware/openapi-proto-messages/blob/a9676f27f40b60569fb8a510aeadedba901b74e9/OpenApiMessages.proto),
[model schema](https://github.com/spotware/openapi-proto-messages/blob/a9676f27f40b60569fb8a510aeadedba901b74e9/OpenApiModelMessages.proto).

## The plugin SDK lead

The separate plugin SDK's `ProtoOrder` model contains `ocoOrderId`, described as
the identifier of a related OCO order. The model documentation does not establish
whether this is reserved, internal, limited to protection relationships, or usable
for arbitrary entry orders. It would be unjustified to assert that it is
specifically SL/TP-only. Source: [plugin order model](https://help.ctrader.com/plugins/developers/all-apps/sdk-references/public-server-model/#protoorder).

The documented plugin requests `ProtoCreateNewOrderReq`, `ProtoModifyOrderReq`,
and `ProtoModifyOrderProtectionReq` do not accept `ocoOrderId` or another OCO
relationship field. The published request-type list also exposes no OCO linking
operation. A returned model field therefore does not demonstrate a public creation
mechanism, even through that separate SDK. Source: [plugin server requests](https://help.ctrader.com/plugins/developers/all-apps/sdk-references/public-server-message/).

## Other names and historical material

Searches covered OCO, one-cancels-other, linked orders, bracket orders, and
contingent/group relationships. Current Open API documentation describes
position-linked orders, but those identifiers do not specify cancellation of a
sibling pending entry. Source: [Open API order model](https://help.ctrader.com/open-api/model-messages/#protooaorder).

A vendor roadmap thread from 2016 described a planned feature linking two pending
orders and cancelling the sibling after a fill. It is historical intent, not a
current Open API specification or release confirmation. Source: [historical
roadmap](https://community.ctrader.com/forum/ctrader-support/9267/).

## Planning implication and remaining uncertainty

Retain the current v1 exclusion of arbitrary entry OCO unless Spotware supplies a
supported API operation and semantics. Do not confuse this exclusion with native
position protection or advanced take-profit support. Application-managed sibling
cancellation is possible as a separate design, but requires durable relationship
state, execution-event handling, cancellation-failure policy, and reconciliation;
it is not a broker-atomic OCO guarantee.

No vendor inquiry was sent. The unresolved question is whether a newer or
unpublished supported operation exists outside the inspected public contract.
Documentation/schema inspection cannot establish runtime availability of such an
operation. This note records evidence, not an implementation or demo validation.
