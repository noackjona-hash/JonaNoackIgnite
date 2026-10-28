package main

import (
	"fmt"

	"github.com/lxn/walk"
)

// ── Herde & Hotspots Table Model ─────────────────────────────────────────────
type HotspotItem struct {
	ID         int
	Class      string
	Risk       string
	MaxTemp    string
	DeltaT     string
	AreaMm2    string
	Confidence string
	Score      string
}

type HotspotModel struct {
	walk.TableModelBase
	items []*HotspotItem
}

func NewHotspotModel() *HotspotModel {
	return &HotspotModel{items: make([]*HotspotItem, 0)}
}

func (m *HotspotModel) RowCount() int {
	return len(m.items)
}

func (m *HotspotModel) Value(row, col int) interface{} {
	if row < 0 || row >= len(m.items) {
		return nil
	}
	item := m.items[row]
	switch col {
	case 0:
		return item.ID
	case 1:
		return item.Class
	case 2:
		return item.Risk
	case 3:
		return item.MaxTemp
	case 4:
		return item.DeltaT
	case 5:
		return item.AreaMm2
	case 6:
		return item.Confidence
	}
	return nil
}

func (m *HotspotModel) SetItems(items []*HotspotItem) {
	m.items = items
	m.PublishRowsReset()
}

// ── 5-Zonen Bilateralvergleich Table Model ──────────────────────────────────
type ZoneItem struct {
	Name   string
	Left   string
	Right  string
	DeltaT string
	Status string
}

type ZoneModel struct {
	walk.TableModelBase
	items []*ZoneItem
}

func NewZoneModel() *ZoneModel {
	return &ZoneModel{items: make([]*ZoneItem, 0)}
}

func (m *ZoneModel) RowCount() int {
	return len(m.items)
}

func (m *ZoneModel) Value(row, col int) interface{} {
	if row < 0 || row >= len(m.items) {
		return nil
	}
	item := m.items[row]
	switch col {
	case 0:
		return item.Name
	case 1:
		return item.Left
	case 2:
		return item.Right
	case 3:
		return item.DeltaT
	case 4:
		return item.Status
	}
	return nil
}

func (m *ZoneModel) SetItems(items []*ZoneItem) {
	m.items = items
	m.PublishRowsReset()
}

// ── 42-Stufen Pipeline Timing Table Model ───────────────────────────────────
type StageItem struct {
	StageNum int
	Name     string
	Duration string
}

type StageModel struct {
	walk.TableModelBase
	items []*StageItem
}

func NewStageModel() *StageModel {
	return &StageModel{items: make([]*StageItem, 0)}
}

func (m *StageModel) RowCount() int {
	return len(m.items)
}

func (m *StageModel) Value(row, col int) interface{} {
	if row < 0 || row >= len(m.items) {
		return nil
	}
	item := m.items[row]
	switch col {
	case 0:
		return item.StageNum
	case 1:
		return item.Name
	case 2:
		return item.Duration
	}
	return nil
}

func (m *StageModel) SetItems(items []*StageItem) {
	m.items = items
	m.PublishRowsReset()
}

// ── DSGVO Art. 30 Audit-Trail Table Model ───────────────────────────────────
type AuditTableItem struct {
	Timestamp string
	PatientID string
	Action    string
	Hotspots  int
	Risk      string
	Duration  string
	Hash      string
}

type AuditModel struct {
	walk.TableModelBase
	items []*AuditTableItem
}

func NewAuditModel() *AuditModel {
	return &AuditModel{items: make([]*AuditTableItem, 0)}
}

func (m *AuditModel) RowCount() int {
	return len(m.items)
}

func (m *AuditModel) Value(row, col int) interface{} {
	if row < 0 || row >= len(m.items) {
		return nil
	}
	item := m.items[row]
	switch col {
	case 0:
		return item.Timestamp
	case 1:
		return item.PatientID
	case 2:
		return item.Action
	case 3:
		return item.Hotspots
	case 4:
		return item.Risk
	case 5:
		return item.Duration
	case 6:
		if len(item.Hash) > 16 {
			return item.Hash[:16] + "..."
		}
		return item.Hash
	}
	return nil
}

func (m *AuditModel) SetItems(items []*AuditTableItem) {
	m.items = items
	m.PublishRowsReset()
}

func formatFloat(v float64, prec int) string {
	return fmt.Sprintf("%.*f", prec, v)
}
