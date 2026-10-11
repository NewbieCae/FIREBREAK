// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title FirebreakRegistry — timestamped witness of Firebreak proofs
/// @notice Holds no business data: only fingerprints (sha256) of audit logs,
///         signed alerts and incident declarations, plus the directory of
///         members and their Ed25519 keys.
///         The contract decides nothing: it attests who wrote what, and when.
contract FirebreakRegistry {
    struct Member {
        bytes32 companyId;
        bytes32 ed25519PubKey;
        bool active;
    }

    struct AlertRecord {
        bytes32 fromCompany;
        bytes32 toCompany;
        uint8 alertType; // 0 = taint, 1 = release, 2 = report (upstream quality report)
        uint64 anchoredAt;
        uint64 ackAt;
    }

    struct AuditAnchor {
        bytes32 head;
        uint32 entries;
        uint64 anchoredAt;
    }

    address public admin;
    mapping(address => Member) public members;
    mapping(bytes32 => address) public accountOf;
    mapping(bytes32 => bytes32) public pubKeyOf;
    mapping(bytes32 => AlertRecord) public alerts;
    mapping(bytes32 => mapping(bytes32 => AuditAnchor)) public latestAudit;

    error NotAdmin();
    error NotMember();
    error ZeroValue();
    error CompanyTaken(bytes32 companyId, address account);
    error AlertAlreadyAnchored(bytes32 alertHash);
    error UnknownAlert(bytes32 alertHash);
    error NotRecipient(bytes32 alertHash);
    error AlreadyAcknowledged(bytes32 alertHash);
    error InvalidAlertType(uint8 alertType);
    error AuditShrunk(uint32 previous, uint32 submitted);

    event AdminTransferred(address indexed previousAdmin, address indexed newAdmin);
    event MemberRegistered(address indexed account, bytes32 indexed companyId, bytes32 ed25519PubKey);
    event MemberDeactivated(address indexed account, bytes32 indexed companyId);
    event IncidentDeclared(
        bytes32 indexed runId,
        bytes32 indexed declarer,
        bytes32 indexed sourceCompany,
        uint64 since,
        bytes32 declarationHash,
        uint64 timestamp
    );
    event IncidentWithdrawn(
        bytes32 indexed runId,
        bytes32 indexed declarer,
        bytes32 indexed sourceCompany,
        bytes32 declarationHash,
        uint64 timestamp
    );
    event AlertAnchored(
        bytes32 indexed runId,
        bytes32 indexed alertHash,
        bytes32 indexed fromCompany,
        bytes32 toCompany,
        uint8 alertType,
        uint64 timestamp
    );
    event AlertAcknowledged(bytes32 indexed alertHash, bytes32 indexed toCompany, uint64 timestamp);
    event AuditAnchored(
        bytes32 indexed runId,
        bytes32 indexed companyId,
        bytes32 head,
        uint32 entries,
        uint64 timestamp
    );

    modifier onlyAdmin() {
        if (msg.sender != admin) revert NotAdmin();
        _;
    }

    modifier onlyMember() {
        if (!members[msg.sender].active) revert NotMember();
        _;
    }

    constructor() {
        admin = msg.sender;
        emit AdminTransferred(address(0), msg.sender);
    }

    function transferAdmin(address newAdmin) external onlyAdmin {
        if (newAdmin == address(0)) revert ZeroValue();
        emit AdminTransferred(admin, newAdmin);
        admin = newAdmin;
    }

    /// @notice Creates or updates a member. A companyId can be bound to only one account.
    function registerMember(address account, bytes32 companyId, bytes32 pubKey) external onlyAdmin {
        if (account == address(0) || companyId == bytes32(0)) revert ZeroValue();
        address current = accountOf[companyId];
        if (current != address(0) && current != account) revert CompanyTaken(companyId, current);
        bytes32 previous = members[account].companyId;
        if (previous != bytes32(0) && previous != companyId) {
            delete accountOf[previous];
            delete pubKeyOf[previous];
        }
        members[account] = Member(companyId, pubKey, true);
        accountOf[companyId] = account;
        pubKeyOf[companyId] = pubKey;
        emit MemberRegistered(account, companyId, pubKey);
    }

    function deactivateMember(address account) external onlyAdmin {
        Member storage m = members[account];
        if (!m.active) revert NotMember();
        m.active = false;
        emit MemberDeactivated(account, m.companyId);
    }

    function declareIncident(bytes32 runId, bytes32 sourceCompany, uint64 since, bytes32 declarationHash)
        external
        onlyMember
    {
        emit IncidentDeclared(
            runId, members[msg.sender].companyId, sourceCompany, since, declarationHash, uint64(block.timestamp)
        );
    }

    function withdrawIncident(bytes32 runId, bytes32 sourceCompany, bytes32 declarationHash) external onlyMember {
        emit IncidentWithdrawn(
            runId, members[msg.sender].companyId, sourceCompany, declarationHash, uint64(block.timestamp)
        );
    }

    /// @notice The issuer of a signed alert (or of a quality report) anchors its fingerprint.
    function anchorAlert(bytes32 runId, bytes32 alertHash, bytes32 toCompany, uint8 alertType) external onlyMember {
        if (alertType > 2) revert InvalidAlertType(alertType);
        if (alertHash == bytes32(0) || toCompany == bytes32(0)) revert ZeroValue();
        if (alerts[alertHash].anchoredAt != 0) revert AlertAlreadyAnchored(alertHash);
        bytes32 fromCompany = members[msg.sender].companyId;
        alerts[alertHash] = AlertRecord(fromCompany, toCompany, alertType, uint64(block.timestamp), 0);
        emit AlertAnchored(runId, alertHash, fromCompany, toCompany, alertType, uint64(block.timestamp));
    }

    /// @notice The recipient acknowledges receipt: proof that it was notified, and when.
    function acknowledgeAlert(bytes32 alertHash) external onlyMember {
        AlertRecord storage a = alerts[alertHash];
        if (a.anchoredAt == 0) revert UnknownAlert(alertHash);
        if (a.toCompany != members[msg.sender].companyId) revert NotRecipient(alertHash);
        if (a.ackAt != 0) revert AlreadyAcknowledged(alertHash);
        a.ackAt = uint64(block.timestamp);
        emit AlertAcknowledged(alertHash, a.toCompany, uint64(block.timestamp));
    }

    /// @notice Anchors the head of the caller's audit log. A log never gets shorter.
    function anchorAudit(bytes32 runId, bytes32 head, uint32 entries) external onlyMember {
        bytes32 companyId = members[msg.sender].companyId;
        AuditAnchor storage last = latestAudit[runId][companyId];
        if (entries < last.entries) revert AuditShrunk(last.entries, entries);
        latestAudit[runId][companyId] = AuditAnchor(head, entries, uint64(block.timestamp));
        emit AuditAnchored(runId, companyId, head, entries, uint64(block.timestamp));
    }
}
